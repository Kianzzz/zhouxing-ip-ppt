#!/usr/bin/env python3
"""Audit palette provenance and evidence/device insertion; no aesthetic scoring."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path


def audit(plan, base, stage='plan', readback=None):
    errors, warnings = [], []
    def fail(where, message):
        errors.append(f'{where}: {message}')
    def local(value):
        return (base / value).resolve() if isinstance(value, str) and value else None
    def same_image(a, b):
        left, right = local(a), local(b)
        if left == right: return left is not None
        # Identical shared frames can have multiple local paths but one upload token.
        if not left or not right or not left.is_file() or not right.is_file(): return False
        return hashlib.sha256(left.read_bytes()).digest() == hashlib.sha256(right.read_bytes()).digest()
    def check_file(value, where):
        p = local(value)
        if p is None or not p.is_file():
            fail(where, 'missing local file'); return None
        return p
    if not isinstance(plan, dict):
        return {'errors': ['plan must be an object'], 'warnings': []}
    palette = plan.get('palette_contract')
    if not isinstance(palette, dict):
        fail('palette', 'missing palette_contract')
    else:
        if palette.get('source_kind') not in ('explicit', 'visual-reference', 'character-derived', 'content-derived', 'fallback'):
            fail('palette', 'unknown source_kind')
        refs = palette.get('source_refs')
        if not isinstance(refs, list):
            fail('palette', 'source_refs must be an array')
        elif palette.get('source_kind') in ('visual-reference', 'character-derived') and not refs:
            fail('palette', 'selected source requires actual references')
        else:
            for i, ref in enumerate(refs):
                if not isinstance(ref, dict) or not ref.get('path') or not ref.get('role'):
                    fail('palette', f'reference {i} needs path/role')
                elif stage == 'delivery':
                    check_file(ref['path'], f'palette reference {i}')
        for key in ('rationale', 'page_strategy'):
            if not isinstance(palette.get(key), str) or not palette[key].strip():
                fail('palette', 'missing ' + key)
        roles = palette.get('roles', {})
        if not isinstance(roles, dict): roles = {}
        for key in ('background', 'environment', 'text', 'accent'):
            role = roles.get(key)
            if not isinstance(role, dict):
                fail('palette', 'missing role ' + key); continue
            colors = role.get('colors')
            if not isinstance(colors, list) or not colors or any(not isinstance(c, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in colors):
                fail('palette ' + key, 'colors must be #RRGGBB array')
            if not role.get('source') or not role.get('usage'):
                fail('palette ' + key, 'needs source/usage')
        # One hue is allowed; a count of hues cannot establish visual quality.
    actual_slides = {}
    if stage == 'delivery':
        if not isinstance(readback, dict) or not isinstance(readback.get('slides'), list):
            fail('delivery', 'requires normalized final readback objects')
        else:
            for s in readback['slides']:
                if isinstance(s, dict): actual_slides[s.get('slide_no')] = s
    slides = plan.get('slides')
    if not isinstance(slides, list) or not slides:
        fail('plan', 'slides must be non-empty array'); slides = []
    try:
        manifest = json.loads((Path(__file__).resolve().parent.parent / 'assets/device-mockups/manifest.json').read_text())
        known_templates = set(manifest['templates'])
    except (OSError, ValueError, KeyError, TypeError):
        fail('templates', 'cannot read bundled manifest'); known_templates = set()
    for slide in slides:
        if not isinstance(slide, dict):
            fail('slide', 'must be object'); continue
        number = slide.get('slide_no'); where = f'slide {number}'
        entries = slide.get('evidence_images')
        if not isinstance(entries, list):
            fail(where, 'evidence_images must inventory screenshots/case images, or be []'); entries = []
        objects = actual_slides.get(number, {}).get('objects', [])
        if not isinstance(objects, list): objects = []
        by_id = {o.get('id'): o for o in objects if isinstance(o, dict)}
        if stage == 'delivery' and number not in actual_slides:
            fail(where, 'not present in final readback')
        declared, ids = set(), set()
        for entry in entries:
            if not isinstance(entry, dict):
                fail(where, 'evidence entry must be object'); continue
            ident = entry.get('id'); label = where + ' evidence ' + str(ident)
            if not isinstance(ident, str) or not ident or ident in ids:
                fail(label, 'missing/duplicate id')
            else: ids.add(ident)
            for key in ('source', 'media_kind', 'purpose', 'protected_content'):
                if not entry.get(key): fail(label, 'missing ' + key)
            treatment = entry.get('treatment')
            if treatment not in ('device', 'plain', 'already-framed'):
                fail(label, 'unknown treatment'); continue
            if treatment != 'device' and not entry.get('reason'):
                fail(label, 'unframed/already-framed image requires a reason')
            object_ids = entry.get('object_ids')
            valid_ids = isinstance(object_ids, list) and object_ids and all(isinstance(x, str) and x for x in object_ids)
            if not valid_ids or len(set(object_ids)) != len(object_ids):
                fail(label, 'object_ids must contain distinct planned/final IDs'); object_ids = []
            declared.update(object_ids)
            expected_files = []
            if treatment == 'device':
                if entry.get('template') not in known_templates: fail(label, 'unknown device template')
                mode = entry.get('mode')
                if mode not in ('layered', 'composite'): fail(label, 'mode must be layered/composite')
                keys = ('screen', 'frame') if mode == 'layered' else ('composite',)
                files = entry.get('files', {})
                if not isinstance(files, dict): files = {}
                for key in (*keys, 'placement'):
                    if not files.get(key): fail(label, 'missing files.' + key)
                expected_files = [files.get(k) for k in keys]
                if len(object_ids) != len(keys): fail(label, 'object count does not match device mode (screen/frame may be missing)')
                if stage == 'delivery':
                    pp = check_file(files.get('placement'), label + ' placement')
                    if pp:
                        try:
                            place = json.loads(pp.read_text())
                            if place.get('device') != entry.get('template'): fail(label, 'placement template mismatch')
                            if local(place.get('input')) != local(entry.get('source')): fail(label, 'placement source mismatch')
                            if not place.get('visible_source_rect'): fail(label, 'entire screenshot is cropped out')
                        except (OSError, ValueError, AttributeError): fail(label, 'invalid placement JSON')
            else:
                expected_files = [entry.get('source')]
                if len(object_ids) != 1: fail(label, 'plain/already-framed expects one image object')
            if stage != 'delivery': continue
            check_file(entry.get('source'), label + ' source')
            for oid, file in zip(object_ids, expected_files):
                check_file(file, label + ' output')
                obj = by_id.get(oid)
                if not obj or obj.get('type') != 'image':
                    fail(label, 'image object not inserted: ' + oid); continue
                if not same_image(obj.get('file'), file): fail(label, 'inserted image file mismatch: ' + oid)
            if treatment == 'device' and entry.get('mode') == 'layered' and len(object_ids) == 2:
                screen, frame = (by_id.get(x, {}) for x in object_ids)
                boxes = [o.get('bbox') for o in (screen, frame)]
                valid_boxes = all(isinstance(b, list) and len(b) == 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in b) and min(b[2:]) > 0 for b in boxes)
                if not valid_boxes or any(abs(a-b) > .5 for a,b in zip(*boxes)):
                    fail(label, 'screen/frame must share a valid display box')
                order = [o.get('layer_index') for o in (screen, frame)]
                if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in order) or order[0] >= order[1]:
                    fail(label, 'frame must be above screen in final layer order')
        for obj in objects:
            if isinstance(obj, dict) and obj.get('kind') == 'evidence' and obj.get('id') not in declared:
                fail(where, 'unreviewed evidence object: ' + str(obj.get('id')))
    return {'errors': errors, 'warnings': warnings, 'stage': stage,
            'limits': 'Provenance and insertion checks only; inspect final slide previews for color relationships, visible frame, crop and legibility.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('plan', type=Path)
    ap.add_argument('--stage', choices=('plan', 'delivery'), default='plan')
    ap.add_argument('--objects', type=Path)
    args = ap.parse_args()
    try:
        plan = json.loads(args.plan.read_text())
        root = plan.get('asset_base', '.') if isinstance(plan, dict) else '.'
        base = (args.plan.resolve().parent / root).resolve()
        actual = json.loads(args.objects.read_text()) if args.objects else None
        result = audit(plan, base, args.stage, actual)
    except (OSError, ValueError, TypeError) as exc:
        result = {'errors': [str(exc)], 'warnings': []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit palette provenance and evidence/device insertion; no aesthetic scoring."""
import argparse
import colorsys
import hashlib
import json
import math
import re
from pathlib import Path


def hex_color(value):
    return isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) is not None


def neutral_or_primary(color, primary):
    """Conservative hue guard, not a judgment of color harmony or prominence."""
    rgb = tuple(int(color[i:i+2], 16) / 255 for i in (1, 3, 5))
    if max(rgb) - min(rgb) <= 24 / 255:
        return True
    hue = colorsys.rgb_to_hsv(*rgb)[0]
    for base in primary:
        brgb = tuple(int(base[i:i+2], 16) / 255 for i in (1, 3, 5))
        if max(brgb) - min(brgb) <= 24 / 255:
            continue
        difference = abs(hue - colorsys.rgb_to_hsv(*brgb)[0])
        if min(difference, 1 - difference) <= 15 / 360:
            return True
    return False


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
    declared_native = set()
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
        for key in ('primary', 'background', 'environment', 'text', 'accent'):
            role = roles.get(key)
            if not isinstance(role, dict):
                fail('palette', 'missing role ' + key); continue
            colors = role.get('colors')
            if not isinstance(colors, list) or not colors or any(not isinstance(c, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in colors):
                fail('palette ' + key, 'colors must be #RRGGBB array')
            if not role.get('source') or not role.get('usage'):
                fail('palette ' + key, 'needs source/usage')
        primary = roles.get('primary', {}).get('colors', []) if isinstance(roles.get('primary'), dict) else []
        primary = [c.upper() for c in primary if hex_color(c)] if isinstance(primary, list) else []
        secondary = palette.get('secondary_colors')
        approved, status_only = set(), set()
        if not isinstance(secondary, list):
            fail('palette', 'secondary_colors must be an array, or []'); secondary = []
        reference_paths = {r.get('path') for r in refs if isinstance(r, dict) and isinstance(r.get('path'), str)} if isinstance(refs, list) else set()
        for entry in secondary:
            if not isinstance(entry, dict) or not hex_color(entry.get('color')):
                fail('palette secondary', 'needs a #RRGGBB color'); continue
            color = entry['color'].upper(); kind = entry.get('source_kind')
            if kind not in ('explicit', 'visual-reference', 'semantic') or not entry.get('source'):
                fail('palette secondary ' + color, 'needs explicit/reference/semantic source evidence'); continue
            if kind == 'visual-reference' and entry.get('source_ref') not in reference_paths:
                fail('palette secondary ' + color, 'source_ref must match a designated palette reference'); continue
            (status_only if kind == 'semantic' else approved).add(color)
        for key in ('primary', 'background', 'text', 'accent'):
            role = roles.get(key)
            colors = role.get('colors', []) if isinstance(role, dict) else []
            if not isinstance(colors, list): continue
            for color in colors:
                if not hex_color(color): continue
                color = color.upper(); declared_native.add(color)
                allowed = approved | (status_only if key in ('text', 'accent') else set())
                if not neutral_or_primary(color, primary) and color not in allowed:
                    fail('palette ' + key, 'unsupported secondary hue ' + color)
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
        if stage == 'delivery':
            native_colors = actual_slides.get(number, {}).get('native_colors')
            if not isinstance(native_colors, list) or not native_colors or any(not hex_color(c) for c in native_colors):
                fail(where, 'readback needs actual native_colors as a non-empty #RRGGBB array')
            else:
                for color in native_colors:
                    if color.upper() not in declared_native:
                        fail(where, 'actual native color outside declared palette: ' + color.upper())
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
            'limits': 'Primary/secondary source and actual-color guards plus insertion checks only. Hue/near-neutral tolerance is geometric color grouping, not evidence that the source is truthful or the primary visually dominates. Inspect final previews for area hierarchy, harmony, frame, crop and legibility.'}


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

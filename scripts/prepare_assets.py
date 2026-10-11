"""Copy final PNGs unchanged; derive only tiny HUD portrait templates from screenshots."""
import argparse
import json
from pathlib import Path
import shutil
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKINS = [
    ('sigma', 'Sigma', 'Hielo', '01_hielo'),
    ('ramattra', 'Ramattra', 'Robot amarillo', '02_robot_amarillo'),
    ('mauga', 'Mauga', 'Guerrero rojo', '03_guerrero_rojo'),
    ('sombra', 'Sombra', 'Felina morada', '04_felina_morada'),
    ('illari', 'Illari', 'Verano', '05_verano_naranja'),
    ('ashe', 'Ashe', 'Novia rosa', '06_novia_rosa'),
    ('sojourn', 'Sojourn', 'Cibernética blanca', '07_cibernetica_blanca'),
    ('cassidy', 'Cassidy', 'Detective', '08_detective'),
    ('genji', 'Genji', 'Caballero azul', '09_caballero_azul'),
    ('junker-queen', 'Junker Queen', 'Gladiadora', '10_gladiadora_roja'),
]



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sprites', type=Path, required=True)
    parser.add_argument('--base-open', type=Path, required=True)
    parser.add_argument('--base-closed', type=Path, required=True)
    parser.add_argument('--screenshots', type=Path, required=True, help='Private JSON mapping hero IDs to input files')
    parser.add_argument('--legacy-junker', type=Path)
    args = parser.parse_args()
    avatars, portraits = ROOT / 'dist/assets/avatars', ROOT / 'dist/assets/portraits'
    avatars.mkdir(parents=True, exist_ok=True)
    portraits.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.base_open, avatars / 'base-talk.png')
    shutil.copyfile(args.base_closed, avatars / 'base-idle.png')
    screenshots = json.loads(args.screenshots.read_text(encoding='utf-8'))
    heroes = [dict(id='base', name='Richard', skin='Original', idle='assets/avatars/base-idle.png',
                   talk='assets/avatars/base-talk.png', portrait=None, calibrated=False)]
    for hero, name, skin, prefix in SKINS:
        for state, suffix in [('idle', 'cerrada'), ('talk', 'abierta')]:
            source = args.sprites / f'{prefix}_boca_{suffix}.png'
            with Image.open(source) as image:
                if image.size != (1254, 1254) or image.mode != 'RGBA':
                    raise ValueError(f'PNG incompatible: {source.name}')
            shutil.copyfile(source, avatars / f'{hero}-{state}.png')
        if hero in screenshots:
            with Image.open(screenshots[hero]) as image:
                frame = image.convert('RGB').resize((1920, 1080), Image.Resampling.BILINEAR)
                # Only the icon's interior, not the blue frame, health, nickname or chat.
                frame.crop((62, 888, 150, 997)).save(portraits / f'{hero}.png')
        elif hero == 'junker-queen' and args.legacy_junker:
            shutil.copyfile(args.legacy_junker, portraits / f'{hero}.png')
        heroes.append(dict(id=hero, name=name, skin=skin, idle=f'assets/avatars/{hero}-idle.png',
                           talk=f'assets/avatars/{hero}-talk.png', portrait=f'assets/portraits/{hero}.png',
                           calibrated=hero in screenshots))
    (ROOT / 'dist/catalog.json').write_text(json.dumps(dict(version=1, heroes=heroes), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(heroes)} avatares: PNGs originales copiados sin recomprimir; {len(screenshots)} retratos calibrados.')


if __name__ == '__main__':
    main()

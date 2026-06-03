from pathlib import Path

script_path = Path(__file__)
print(script_path.cwd())
# /home/PR.RT.RU/v.karitsky/work/tools/pathlib_
DATA_DIR  = script_path.parent 
DATA_FILE = DATA_DIR / 'one.txt'
content = DATA_FILE.read_text(encoding='utf-8')
content = f'{content}\n2'
OUT_FILE = DATA_DIR / 'two.txt'
OUT_FILE.write_text(content, encoding='utf-8')
Path('three.txt').write_text(content, encoding='utf-8')

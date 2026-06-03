from pathlib import Path

script_path = Path(__file__)

# print(f'script_path: {script_path}')
# print(f'script_path.parent: {script_path.parent}')
# print(f'script_path.name: {script_path.name}')
# print(f'script_path.is_dir: {script_path.is_dir()}')
# print(f'script_path.is_file: {script_path.is_file()}')
# print(f'script_path.parts: {script_path.parts}')
# print(f'script_path.exists: {script_path.exists()}')
# print(f'script_path.stat: {script_path.stat()}')
# print(f'script_path.suffix: {script_path.suffix}')
# print(f'script_path.stem {script_path.stem}')

'''
script_path: /home/PR.RT.RU/v.karitsky/work/tools/pathlib_/path_01.py
script_path.parent: /home/PR.RT.RU/v.karitsky/work/tools/pathlib_
script_path.name: path_01.py
script_path.is_dir: False
script_path.is_file: True
script_path.parts: ('/', 'home', 'PR.RT.RU', 'v.karitsky', 'work', 'tools', 'pathlib_', 'path_01.py')
script_path.exists: True
script_path.stat: os.stat_result(st_mode=33188, st_ino=850819, st_dev=36, st_nlink=1, st_uid=10002, st_gid=10000, st_size=624, st_atime=1764741799, st_mtime=1764741798, st_ctime=1764741798)
script_path.suffix: .py
script_path.stem path_01
.parent'''

PATHS = script_path.parent 

for path in PATHS.glob('*.txt'):
   print(f'File name {path.name}, size {path.stat().st_size}')
print('_'*40)  
for path in PATHS.glob('**/*.txt'):
   print(f'File name {path.name}, size {path.stat().st_size}')   

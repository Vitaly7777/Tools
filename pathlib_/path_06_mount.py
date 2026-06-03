from pathlib import Path

def test_mount(path_mnt:str = '/mnt/dfs/РУЗ') -> bool:
    path_mnt = Path('/mnt/dfs/РУЗ')
    return path_mnt.is_dir()

if __name__ == "__main__":
    print(test_mount())

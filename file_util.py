from pathlib import Path

def test_mount(path_mnt:str = '/mnt/dfs/РУЗ') -> bool:
    return Path(path_mnt).is_dir()


def replaced_path_mnt(path:str, share_path:str = '//pr.rt.ru/fspr/руз/', mnt_path:str = '/mnt/dfs/РУЗ/'):
    if isinstance(path, str):
        return path.replace('\\', '/').lower().replace(share_path.lower(), mnt_path)
    else:
        return path

if __name__ == "__main__":
    import pandas as pd

    path_str = '\\\\pr.rt.ru\\FSPR\\РУЗ\\Общие_вопросы_ЦК\\Обучение\\Python_проекты\\автоматизация_дзо\\Модель КПЭ.xlsx'
    if test_mount():
        path_mnt = Path(replaced_path_mnt(path_str))
        if path_mnt.exists():
            df2 = pd.read_excel(path_mnt, sheet_name='РТКомм КПЭ OIBDA', header=2)
            print(df2)
        else:
            print('Файл не найден')
    else:
        print('Нет монтирования')

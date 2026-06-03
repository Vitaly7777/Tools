import sys
import pandas as pd 

from PyQt5.QtWidgets import QApplication, QMessageBox
from smb_utils2 import load_df, mnt_or_smb, replaced_path_mnt
# from smb_utils2 import load_smb_credentials, smb_read_df, mnt_read_df, write_df,read_list_obj, read_named_range, test_mount, replaced_path_mnt, MyCustomError
# from smb_utils import load_smb_credentials, read_df, write_df,read_list_obj, read_named_range
SHARE_PATH = '//pr.rt.ru/fspr/руз/'
MNT_PATH = '/mnt/dfs/РУЗ1/'


def main():
    app = QApplication(sys.argv)
    # path_source = '\\\\pr.rt.ru\\FSPR\\РУЗ\\Общие_вопросы_ЦК\\Обучение\\Python_проекты\\автоматизация_дзо\\Модель КПЭ.xlsx'
    # sec = mnt_or_smb(mnt_path=MNT_PATH)
    # if isinstance(sec, bool) and not sec:
    #     path_source = replaced_path_mnt(path_source, SHARE_PATH, MNT_PATH)
    # my_df = load_df(sec, path_source, sheet_name='РТКомм КПЭ OIBDA', header=2)
    sec = mnt_or_smb(mnt_path=MNT_PATH)
    my_df = load_source(sec)
    if isinstance(my_df, pd.DataFrame):
        print(my_df)

def load_source(sec):
    
    # sec = mnt_or_smb(mnt_path=MNT_PATH)
    path_source = '\\\\pr.rt.ru\\FSPR\\РУЗ\\Общие_вопросы_ЦК\\Обучение\\Python_проекты\\автоматизация_дзо\\Модель КПЭ.xlsx'
    if isinstance(sec, bool) and not sec:
        path_source = replaced_path_mnt(path_source, SHARE_PATH, MNT_PATH)
    df1 = load_df(sec, path_source, sheet_name='РТКомм КПЭ OIBDA', header=2)
    return df1

def write_target(sec):
    path_target = '\\\\pr.rt.ru\\FSPR\\РУЗ\\Общие_вопросы_ЦК\\Обучение\\Python_проекты\\автоматизация_дзо\\Test\\test_01.xlsx'


if __name__ == '__main__':
    main()

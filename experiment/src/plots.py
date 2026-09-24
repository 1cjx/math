"""兼容旧入口；统一重建全部当次中文图，避免混入旧英语图或旧Q3结果。"""
from paper_figures import make_paper_figures
def generate_plots(root):
    return make_paper_figures(root)

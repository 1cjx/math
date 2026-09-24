"""在D_scientific_redesign根目录运行：python redraw_selected_local.py F151 F152"""
import argparse
import re
from matplotlib import pyplot as plt
from viz.core import Publisher
from viz.redraw import make_originals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="+")
    args = parser.parse_args()
    selected = {s.upper() for s in args.ids}
    invalid = [s for s in selected if not re.fullmatch(r"F\d{3}", s)
               or not 1 <= int(s[1:]) <= 163]
    if invalid:
        parser.error("图号须为F001–F163：" + ", ".join(sorted(invalid)))

    class SelectedPublisher(Publisher):
        def save(self, fig, code, *values, **kwargs):
            if code in selected:
                return super().save(fig, code, *values, **kwargs)
            plt.close(fig)

    pub = SelectedPublisher()
    originals = {s for s in selected if int(s[1:]) <= 147}
    extras = {s for s in selected if int(s[1:]) >= 148}
    if originals:
        make_originals(pub, originals)
    if extras:
        from viz.extras import make_extras, make_states
        if all(int(s[1:]) >= 160 for s in extras):
            make_states(pub)
        else:
            make_extras(pub)
    written = {r["图号"] for r in pub.records}
    if written != selected:
        raise RuntimeError(f"请求{sorted(selected)}，实际只生成{sorted(written)}")
    pub.finish()
    print("本次实际重画：" + ", ".join(sorted(written)))


if __name__ == "__main__":
    main()

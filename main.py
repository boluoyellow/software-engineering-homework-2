"""游戏入口。

首次运行前请安装第三方库：python -m pip install pygame
"""

try:
    from game import run
except ModuleNotFoundError as error:
    if error.name == "pygame":
        raise SystemExit("缺少 Pygame，请先运行：python -m pip install pygame") from error
    raise


if __name__ == "__main__":
    run()

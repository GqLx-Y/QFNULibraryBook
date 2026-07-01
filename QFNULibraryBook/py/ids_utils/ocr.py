import ddddocr

# 初始化 ddddocr 实例
detector = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)


def slide_match(target_bytes, background_bytes, simple_target=True):
    '''
    使用 ddddocr 计算滑块缺口位置

    Parameters:
        target_bytes: 滑块图片的字节数据
        background_bytes: 背景图片的字节数据
        simple_target: 是否使用简化目标图

    Returns:
        float: 缺口偏移位置
    '''
    result = detector.slide_match(target_bytes, background_bytes, simple_target=simple_target)
    return result


if __name__ == "__main__":
    # 外部函数调用
    with open('target.png', 'rb') as f:
        target_bytes = f.read()
    with open('background.png', 'rb') as f:
        background_bytes = f.read()
    res = slide_match(target_bytes, background_bytes)
    print(res)

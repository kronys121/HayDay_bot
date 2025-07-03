import socket
import sys
import time
import subprocess
import cv2
import numpy as np
import os
import json
import asyncio
import random

from loguru import logger

logger.remove()

logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>",
    colorize=True
)

def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

project_dir = os.path.dirname(os.path.abspath(__file__))

template_dwarf = 'templates\dwarf.png'
template_shape = 'templates\shape.png'
template_crop = 'templates\crop.png' #wheat TODO
template_cancel = 'templates\cancel.png'
template_shop = 'templates\shop.png'
template_empty = 'templates\empty.png'
template_wheat = 'templates\wheat.png'
template_sell = 'templates\sell.png'
template_selling = 'templates\selling.png'
template_adv = 'templates\dav.png'
template_add_adv = r'templates\add_adv.png'
template_lvl_up= 'templates\lvlup.png'
template_decline = 'templates\decline.png'
template_try_again = r'templates\tryagain.png'



def find_and_tap(sock, template, device_id, delay=0.2, pressure=50):
    take_screenshot(device_id)
    coords = find_object(f'screen_{safe_filename(device_id)}.png', template)
    if coords:
        x, y = coords[0]
        tap(sock, x, y, pressure)
        time.sleep(delay)
        return True
    return False

def safe_filename(name):
    return name.replace(":", "_").replace(".", "_")

def take_screenshot(device_id, filename=None):

    filename = f"screen_{safe_filename(device_id)}.png"

    result = subprocess.run(
        ["adb", "-s", device_id, "exec-out", "screencap", "-p"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.returncode != 0 or not result.stdout:
        logger.error(f"Ошибка при снятии скриншота с {safe_filename(device_id)}")
        return False

    with open(filename, "wb") as f:
        f.write(result.stdout)
    return True


def find_object(screen_path, template_path, threshold=0.70, debug=False):
    screen = cv2.imread(screen_path)
    template = cv2.imread(template_path)

    if screen is None or template is None:
        logger.error(f"Не удалось загрузить изображения: {screen_path}, {template_path}")
        return []

    h, w = template.shape[:2]
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    coords = [(pt[0] + w // 2, pt[1] + h // 2) for pt in zip(*locations[::-1])]

    if debug:
        for pt in zip(*locations[::-1]):
            top_left = pt
            bottom_right = (pt[0] + w, pt[1] + h)
            cv2.rectangle(screen, top_left, bottom_right, (0, 255, 0), 2)
            cv2.circle(screen, (pt[0] + w // 2, pt[1] + h // 2), 3, (0, 0, 255), -1)

        debug_path = "debug_result.png"
        cv2.imwrite(debug_path, screen)
        logger.info(f"Отладочное изображение сохранено в {debug_path}")

    return coords

def send_cmd(sock, cmd):
    sock.send((cmd + '\n').encode('utf-8'))
    time.sleep(0.05)

def tap(sock, x, y, pressure=50):
    send_cmd(sock, f'd 0 {x} {y} {pressure}')
    send_cmd(sock, 'c')
    time.sleep(0.05)
    send_cmd(sock, 'u 0')
    send_cmd(sock, 'c')


def find_shape(sock, device_id):
    logger.info(f"{device_id} - Ищу серп...")
    for i in range(1, 22):
        if find_and_tap(sock, template_try_again, device_id ):
            time.sleep(15)
            break
        take_screenshot(device_id)
        coords = find_object(f'screen_{safe_filename(device_id)}.png', template_shape)
        if coords:
            x, y = coords[0]
            return x, y
        else:
            #logger.info(f'{device_id} - Попытка: {i}. Не могу найти серп, жду 10 секунд.')
            time.sleep(10)
    return None

def find_dwarf(sock, device_id):
    for i in range(1, 5):
        time.sleep(0.4)
        take_screenshot(device_id)
        coords = find_object(f'screen_{safe_filename(device_id)}.png', template_dwarf)
        if coords:
            x, y = coords[0]
            logger.info(f"Гном по координатам ({x}, {y})")
            tap(sock, x, y-10)
            time.sleep(1)
            take_screenshot(device_id)
            time.sleep(0.3)
            break

        else:
            logger.warning(f"{device_id} - Гном не найден")

def selling_check(sock, device_id):
    for i in range(1,18):
        take_screenshot(device_id)
        coords = find_object(f'screen_{safe_filename(device_id)}.png',template_selling)
        if coords:
            x, y = coords[0]
            tap(sock, x, y, 50)
        else:
            break

def find_full(sock, device_id):
    logger.info(f'{device_id} - Башня забита... Иду в магазин')
    take_screenshot(device_id)
    coords = find_object(f'screen_{safe_filename(device_id)}.png',template_cancel)
    if coords:
        x, y = coords[0]
        tap(sock, x, y, 50)
        time.sleep(0.3)
        find_crop(sock, device_id)
        time.sleep(0.3)
        go_to_shop(sock, device_id)


def go_to_shop(sock, device_id):

    if find_and_tap(sock, template_shop, device_id ):
        selling_check(sock, device_id)

        for i in range(1, 10):

            if  find_and_tap(sock, template_empty, device_id):

                find_and_tap(sock, template_wheat, device_id)

                find_and_tap(sock,template_sell, device_id)

            else:
                find_and_tap(sock, template_wheat, device_id, 0.3)

                find_and_tap(sock, template_adv, device_id)

                find_and_tap(sock, template_add_adv, device_id)

                find_and_tap(sock, template_cancel, device_id)

                break



def harvest_with_sickle(sock, device_id):
    find_crop(sock, device_id)
    take_screenshot(device_id)
    coords = find_shape(sock, device_id)
    if coords is None:
        logger.warning(f"{device_id} - Серп не найден. Прерываю сбор.")
        return
    x_start, y_start = coords
    zone = (259, 238, 568, 420)  # примерная зона, можно настроить

    swipe_point(sock, x_start, y_start, x_start, y_start, zone)

    # x0, x1 = 259, 568
    # y_start = 420
    # y_end = 238
    # step_size = 4
    #
    # send_cmd(sock, f'd 0 {x_shape} {y_shape} 50')
    # send_cmd(sock, f'd 1 {x_shape} {y_shape} 50')
    # send_cmd(sock, 'c')
    #
    # for y in range(y_start, y_end - 1, -step_size):
    #     send_cmd(sock, f'm 0 {x0} {y} 50')
    #     send_cmd(sock, f'm 1 {x1} {y} 50')
    #     send_cmd(sock, 'c')
    #
    # send_cmd(sock, 'u 0')
    # send_cmd(sock, 'u 1')
    # send_cmd(sock, 'c')
    #
    find_full(sock, device_id)

def get_crop_coord(device_id):
    take_screenshot(device_id)
    coords = find_object(f'screen_{safe_filename(device_id)}.png', template_crop)
    if coords:
        x, y = coords[0]
        #print(f"{device_id} - Пщеница по координатам ({x}, {y})")
        return x, y
    else:
        return None



def generate_points(st_x, st_y, zone):
    combined_points = [(st_x, st_y), (st_x, st_y+10), (st_x+10, st_y), (st_x-10, st_y)]
    y1 = zone[1]
    y2 = zone[3]
    x1 = zone[0]
    x2 = zone[2]

    y = y2
    while y > y1:
        y -= 2
        combined_points.append((x1, y))
        combined_points.append((x2, y))

    combined_points = [(x, y) for x, y in combined_points]

    return combined_points

def swipe_point(sock, x1, y1, x_start, y_start, zone):

    combined_points = generate_points(x_start, y_start, zone)

    sock.send(f"d 0 {x1} {y1} 50\n".encode())
    sock.send(f"d 1 {x1} {y1} 50\n".encode())
    sock.send(b"c\n")
    time.sleep(0.05)

    i = True
    for x, y in combined_points:

        rx = x + random.randint(-1, 2)
        ry = y + random.randint(-1, 2)
        i = not i
        sock.send(f"m {int(i)} {rx} {ry} 50\n".encode())
        if i:
            sock.send(b"c\n")
            time.sleep(0.03)

    sock.send(b"u 0\n")
    sock.send(b"u 1\n")
    sock.send(b"c\n")


def find_crop(sock, device_id):
    take_screenshot(device_id)
    find_dwarf(sock, device_id)
    time.sleep(0.2)
    coords = get_crop_coord(device_id)
    time.sleep(0.2)
    if coords is None:
        #print(f"{device_id} - ❌ Посев не найден")
        return
    x_start, y_start = coords
    zone = (259, 238, 568, 420)

    swipe_point(sock, x_start, y_start, x_start, y_start, zone)

    # x0, x1 = 259, 568
    # y_start = 420
    # y_end = 238
    # step_size = 4
    #
    # send_cmd(sock, f'd 0 {x_crop} {y_crop} 50')
    # send_cmd(sock, f'd 1 {x_crop} {y_crop} 50')
    # send_cmd(sock, 'c')
    #
    # for y in range(y_start, y_end - 1, -step_size):
    #     send_cmd(sock, f'm 0 {x0} {y} 50')
    #     send_cmd(sock, f'm 1 {x1} {y} 50')
    #     send_cmd(sock, 'c')
    #
    # send_cmd(sock, 'u 0')
    # send_cmd(sock, 'u 1')
    # send_cmd(sock, 'c')


def zoom_out(sock,device_id):
    # Пальцы нажали далеко друг от друга
    send_cmd(sock, 'd 0 120 480 50')
    send_cmd(sock, 'd 1 400 480 50')
    send_cmd(sock, 'c')

    # Пальцы двигаются ближе друг к другу
    send_cmd(sock, 'm 0 280 480 50')
    send_cmd(sock, 'm 1 360 480 50')
    send_cmd(sock, 'c')

    send_cmd(sock, 'm 0 320 480 50')
    send_cmd(sock, 'm 1 320 480 50')
    send_cmd(sock, 'c')

    # Отрываем пальцы
    send_cmd(sock, 'u 0')
    send_cmd(sock, 'u 1')
    send_cmd(sock, 'c')

    send_cmd(sock,'d 0 295 390 50')
    send_cmd(sock, 'c')

    send_cmd(sock, 'm 0 620 530 50')
    send_cmd(sock, 'c')

    send_cmd(sock, 'u 0')
    send_cmd(sock, 'c')


    time.sleep(1)


    logger.success(f"{device_id} - Центрировал экран\n")

def start_minitouch(device_id, port):
    """Запуск minitouch и проброс порта под конкретное устройство"""
    device_arg = ["-s", device_id]

    subprocess.Popen(
        ["adb"] + device_arg + ["shell", "/data/local/tmp/minitouch"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1)

    subprocess.run(
        ["adb", "-s", device_id, "forward", f"tcp:{port}", "localabstract:minitouch"],
        check=True
    )

    logger.info(f"{device_id} → порт {port} настроен")

def install_minitouch(device_id):
    arch_map = {
        'x86': 'minitouch-x86',
        'x86_64': 'minitouch',
        'arm64-v8a': 'minitouch-arm64',
        'armeabi-v7a': 'minitouch-armv7',
    }

    abi = subprocess.check_output(["adb", "-s", device_id, "shell", "getprop", "ro.product.cpu.abi"], encoding='utf-8').strip()
    logger.info(f"ABI устройства: {abi}")

    binary_name = arch_map.get(abi)
    if not binary_name:
        print(f"Нет бинарника для ABI: {abi}")
        return False

    local_path = os.path.join("minitouchbin", binary_name)
    remote_path = "/data/local/tmp/minitouch"


    subprocess.run(["adb", "-s", device_id, "push", local_path, remote_path],
                   check=True,
                   stdout = subprocess.DEVNULL,
                   stderr = subprocess.DEVNULL)

    subprocess.run(["adb", "-s", device_id, "shell", "chmod", "755", remote_path],
                   check=True,
                   stdout = subprocess.DEVNULL,
                   stderr = subprocess.DEVNULL)
    logger.success(f"minitouch установлен на {device_id}")

    return True

def connect_to_minitouch(port):
    sock = socket.create_connection(('127.0.0.1', port), timeout=5)
    welcome = sock.recv(4096).decode()
    logger.success(f"Подключено к minitouch на порту {port}")
    logger.debug(f"\n{welcome}")
    return sock

async def process_device(device_id, port):
    try:
        await asyncio.to_thread(install_minitouch, device_id)
        await asyncio.to_thread(start_minitouch, device_id, port)
        sock = await asyncio.to_thread(connect_to_minitouch, port)

        while True:
            logger.info(f"Обработка устройства {device_id}")
            try:
                await asyncio.to_thread(zoom_out, sock, device_id)
                await asyncio.to_thread(take_screenshot, device_id)
                await asyncio.to_thread(harvest_with_sickle, sock, device_id)
                await asyncio.to_thread(find_crop, sock, device_id)

                await asyncio.to_thread(find_and_tap, sock, template_lvl_up, device_id)
                await asyncio.to_thread(find_and_tap, sock, template_decline, device_id)

                await asyncio.to_thread(find_and_tap, sock, template_try_again, device_id)

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f" Ошибка на {device_id}: {e}")
                await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"Ошибка при запуске устройства {device_id}: {e}")

async def main():
    config = load_config()
    devices = [(d["device_id"], d["port"]) for d in config["devices"] if d.get("enabled", True)]

    if not devices:
        logger.warning("Нет активных устройств в конфиге.")
        return

    tasks = [process_device(device_id, port) for device_id, port in devices]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
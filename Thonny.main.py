# thonny
# main.py
# Raspberry Pi Pico W / MicroPython
#
# Grove Light Sensor v1.1
# SIG -> GP27(ADC1)
#
# RGB LED Stick <10-WS2813 Mini>
# DIN -> GP16

import gc
import socket
import ssl
import time
import network

from machine import ADC, Pin
from neopixel import NeoPixel
from wifi_config import WIFI_SSID, WIFI_PASSWORD


# Apps Script에서 배포한 실제 /exec 주소로 변경하세요.
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyXaI6RnXJ_7zeLBwqxt5_pId4kmGgjKbt2_CYv1LzuQsW88E_nYYOZE2_AEtcNHTON4Q/exec"

# 측정 및 전송 주기(초)
INTERVAL = 10

# 핀 설정
LIGHT_SENSOR_PIN = 27
LED_PIN = 16
LED_COUNT = 10

# 조도센서 평균 측정 설정
SAMPLE_COUNT = 20
SAMPLE_DELAY_MS = 20

# WS2813 LED 설정
LED_BRIGHTNESS = 255
LED_COLOR = (
    LED_BRIGHTNESS,
    LED_BRIGHTNESS,
    LED_BRIGHTNESS
)
LED_OFF = (0, 0, 0)

# 등급별 켜지는 LED 개수
GRADE_LED_COUNTS = {
    1: 6,
    2: 5,
    3: 4,
    4: 3,
    5: 2,
    6: 1
}

# 밝을수록 ADC 값이 증가하면 True입니다.
# 손전등을 비췄을 때 ADC 값이 감소하면 False로 변경하세요.
BRIGHTER_IS_HIGHER = True

# BRIGHTER_IS_HIGHER = True일 때 사용하는 경계값
#
# 11400 이상: 1등급, LED 6개
# 11300 이상: 2등급, LED 5개
# 11200 이상: 3등급, LED 4개
# 11100 이상: 4등급, LED 3개
# 11000 이상: 5등급, LED 2개
# 11000 미만: 6등급, LED 1개
GRADE_BOUNDARIES_HIGH = (
    11400,
    11300,
    11200,
    11100,
    11000
)

# BRIGHTER_IS_HIGHER = False일 때 사용하는 경계값
#
# 11000 이하: 1등급, LED 6개
# 11100 이하: 2등급, LED 5개
# 11200 이하: 3등급, LED 4개
# 11300 이하: 4등급, LED 3개
# 11400 이하: 5등급, LED 2개
# 11400 초과: 6등급, LED 1개
GRADE_BOUNDARIES_LOW = (
    11000,
    11100,
    11200,
    11300,
    11400
)

# 통신 설정
WIFI_CONNECT_TIMEOUT = 30
WIFI_RETRY_COUNT = 3
SOCKET_TIMEOUT = 20
MAX_REDIRECTS = 5
MAX_RESPONSE_SIZE = 12288

sensor = ADC(Pin(LIGHT_SENSOR_PIN))
leds = NeoPixel(Pin(LED_PIN, Pin.OUT), LED_COUNT)
wlan = network.WLAN(network.STA_IF)


def clear_leds():
    for index in range(LED_COUNT):
        leds[index] = LED_OFF

    leds.write()


def show_grade(grade):
    on_count = GRADE_LED_COUNTS[grade]

    for index in range(LED_COUNT):
        if index < on_count:
            leds[index] = LED_COLOR
        else:
            leds[index] = LED_OFF

    leds.write()


def value_to_grade(value):
    if BRIGHTER_IS_HIGHER:
        if value >= GRADE_BOUNDARIES_HIGH[0]:
            return 1

        if value >= GRADE_BOUNDARIES_HIGH[1]:
            return 2

        if value >= GRADE_BOUNDARIES_HIGH[2]:
            return 3

        if value >= GRADE_BOUNDARIES_HIGH[3]:
            return 4

        if value >= GRADE_BOUNDARIES_HIGH[4]:
            return 5

        return 6

    if value <= GRADE_BOUNDARIES_LOW[0]:
        return 1

    if value <= GRADE_BOUNDARIES_LOW[1]:
        return 2

    if value <= GRADE_BOUNDARIES_LOW[2]:
        return 3

    if value <= GRADE_BOUNDARIES_LOW[3]:
        return 4

    if value <= GRADE_BOUNDARIES_LOW[4]:
        return 5

    return 6


def read_average():
    total = 0

    for index in range(SAMPLE_COUNT):
        total += sensor.read_u16()

        if index < SAMPLE_COUNT - 1:
            time.sleep_ms(SAMPLE_DELAY_MS)

    return total // SAMPLE_COUNT


def reset_wifi():
    try:
        wlan.disconnect()
    except Exception:
        pass

    try:
        wlan.active(False)
    except Exception:
        pass

    time.sleep_ms(500)
    wlan.active(True)
    time.sleep_ms(500)


def connect_wifi():
    if wlan.isconnected():
        return True

    password = WIFI_PASSWORD

    if password is None:
        password = ""

    password = str(password)

    for attempt in range(1, WIFI_RETRY_COUNT + 1):
        print(
            "Wi-Fi 연결 시도: "
            + str(WIFI_SSID)
            + " ("
            + str(attempt)
            + "/"
            + str(WIFI_RETRY_COUNT)
            + ")"
        )

        reset_wifi()

        try:
            if password == "":
                print("개방형 Wi-Fi 방식")
                wlan.connect(WIFI_SSID)
            else:
                print("비밀번호 방식")
                wlan.connect(WIFI_SSID, password)

            started = time.ticks_ms()

            while True:
                if wlan.isconnected():
                    print("Wi-Fi 연결 완료")
                    print("IP 주소:", wlan.ifconfig()[0])
                    return True

                status = wlan.status()

                if status == -1:
                    print("Wi-Fi 연결 실패")
                    break

                if status == -2:
                    print("Wi-Fi를 찾지 못했습니다.")
                    break

                if status == -3:
                    print("비밀번호 또는 인증 방식 오류")
                    break

                elapsed = time.ticks_diff(
                    time.ticks_ms(),
                    started
                )

                if elapsed >= WIFI_CONNECT_TIMEOUT * 1000:
                    print("Wi-Fi 연결 시간 초과")
                    break

                time.sleep_ms(500)

        except Exception as error:
            print("Wi-Fi 연결 오류:", repr(error))

        try:
            wlan.disconnect()
        except Exception:
            pass

        time.sleep_ms(1000)

    return False


def parse_url(url):
    if url.startswith("https://"):
        scheme = "https"
        remainder = url[8:]
        default_port = 443

    elif url.startswith("http://"):
        scheme = "http"
        remainder = url[7:]
        default_port = 80

    else:
        raise ValueError(
            "URL은 http:// 또는 https://로 시작해야 합니다."
        )

    slash_position = remainder.find("/")

    if slash_position == -1:
        host_port = remainder
        path = "/"
    else:
        host_port = remainder[:slash_position]
        path = remainder[slash_position:]

    colon_position = host_port.rfind(":")

    if colon_position >= 0:
        host = host_port[:colon_position]
        port = int(host_port[colon_position + 1:])
    else:
        host = host_port
        port = default_port

    if host == "":
        raise ValueError("URL에 호스트 이름이 없습니다.")

    return scheme, host, port, path


def make_absolute_url(current_url, location):
    location = location.strip()

    if location.startswith("https://"):
        return location

    if location.startswith("http://"):
        return location

    scheme, host, port, path = parse_url(current_url)

    if scheme == "https" and port == 443:
        origin = scheme + "://" + host
    elif scheme == "http" and port == 80:
        origin = scheme + "://" + host
    else:
        origin = (
            scheme
            + "://"
            + host
            + ":"
            + str(port)
        )

    if location.startswith("//"):
        return scheme + ":" + location

    if location.startswith("/"):
        return origin + location

    slash_position = path.rfind("/")

    if slash_position >= 0:
        base_path = path[:slash_position + 1]
    else:
        base_path = "/"

    return origin + base_path + location


def open_connection(scheme, host, port):
    address = socket.getaddrinfo(
        host,
        port,
        0,
        socket.SOCK_STREAM
    )[0][-1]

    raw_socket = socket.socket()
    raw_socket.settimeout(SOCKET_TIMEOUT)

    try:
        raw_socket.connect(address)

        if scheme == "https":
            try:
                secure_socket = ssl.wrap_socket(
                    raw_socket,
                    server_hostname=host
                )
            except TypeError:
                secure_socket = ssl.wrap_socket(
                    raw_socket
                )

            return secure_socket

        return raw_socket

    except Exception:
        try:
            raw_socket.close()
        except Exception:
            pass

        raise


def receive_all(sock):
    data = b""

    while True:
        try:
            chunk = sock.recv(512)
        except OSError:
            break

        if not chunk:
            break

        data += chunk

        if len(data) >= MAX_RESPONSE_SIZE:
            break

    return data


def decode_chunked(body):
    result = b""
    position = 0

    while position < len(body):
        line_end = body.find(b"\r\n", position)

        if line_end == -1:
            break

        size_text = body[position:line_end]
        semicolon_position = size_text.find(b";")

        if semicolon_position >= 0:
            size_text = size_text[:semicolon_position]

        try:
            chunk_size = int(size_text, 16)
        except ValueError:
            return body

        if chunk_size == 0:
            break

        chunk_start = line_end + 2
        chunk_end = chunk_start + chunk_size

        if chunk_end > len(body):
            break

        result += body[chunk_start:chunk_end]
        position = chunk_end + 2

    return result


def parse_response(data):
    separator_position = data.find(b"\r\n\r\n")

    if separator_position == -1:
        header_data = data
        body = b""
    else:
        header_data = data[:separator_position]
        body = data[separator_position + 4:]

    lines = header_data.split(b"\r\n")

    if len(lines) == 0 or len(lines[0]) == 0:
        raise OSError("HTTP 응답이 비어 있습니다.")

    status_line = lines[0].decode(
        "utf-8",
        "replace"
    )

    status_parts = status_line.split(" ")

    if len(status_parts) < 2:
        raise OSError(
            "잘못된 HTTP 응답: " + status_line
        )

    status_code = int(status_parts[1])
    headers = {}

    for line in lines[1:]:
        colon_position = line.find(b":")

        if colon_position >= 0:
            name = line[:colon_position]
            value = line[colon_position + 1:]

            header_name = name.decode(
                "utf-8",
                "replace"
            ).strip().lower()

            header_value = value.decode(
                "utf-8",
                "replace"
            ).strip()

            headers[header_name] = header_value

    transfer_encoding = headers.get(
        "transfer-encoding",
        ""
    ).lower()

    if "chunked" in transfer_encoding:
        body = decode_chunked(body)

    body_text = body.decode(
        "utf-8",
        "replace"
    )

    return status_code, headers, body_text


def http_get(url):
    current_url = url

    for redirect_count in range(MAX_REDIRECTS + 1):
        scheme, host, port, path = parse_url(
            current_url
        )

        sock = None

        try:
            sock = open_connection(
                scheme,
                host,
                port
            )

            request = (
                "GET "
                + path
                + " HTTP/1.1\r\n"
                + "Host: "
                + host
                + "\r\n"
                + "User-Agent: PicoW-MicroPython\r\n"
                + "Accept: application/json,text/plain,*/*\r\n"
                + "Connection: close\r\n"
                + "\r\n"
            )

            sock.sendall(request.encode("utf-8"))
            response_data = receive_all(sock)

        finally:
            # 성공 여부와 상관없이 소켓을 항상 닫습니다.
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

        status_code, headers, response_body = (
            parse_response(response_data)
        )

        print("HTTP 상태:", status_code)

        if response_body != "":
            print(
                "HTTP 본문:",
                response_body[:500]
            )

        if (
            status_code == 301
            or status_code == 302
            or status_code == 303
            or status_code == 307
            or status_code == 308
        ):
            location = headers.get("location")

            if location is None or location == "":
                raise OSError(
                    "리다이렉트 Location 헤더가 없습니다."
                )

            if redirect_count >= MAX_REDIRECTS:
                raise OSError(
                    "리다이렉트 횟수를 초과했습니다."
                )

            current_url = make_absolute_url(
                current_url,
                location
            )

            print("리다이렉트 이동:", current_url)
            continue

        return status_code, response_body

    raise OSError(
        "HTTP 요청을 완료하지 못했습니다."
    )


def send_value(value, grade, led_count):
    if WEB_APP_URL.find("?") >= 0:
        separator = "&"
    else:
        separator = "?"

    request_url = (
        WEB_APP_URL
        + separator
        + "value="
        + str(int(value))
        + "&grade="
        + str(int(grade))
        + "&ledCount="
        + str(int(led_count))
    )

    print("전송 value:", int(value))
    print("전송 grade:", int(grade))
    print("전송 ledCount:", int(led_count))

    return http_get(request_url)


def validate_settings():
    if not WEB_APP_URL.startswith("https://"):
        raise ValueError(
            "WEB_APP_URL은 https://로 시작해야 합니다."
        )

    if WEB_APP_URL.find("/exec") == -1:
        raise ValueError(
            "WEB_APP_URL은 /exec 주소여야 합니다."
        )

    if WEB_APP_URL.find("실제_배포_ID") >= 0:
        raise ValueError(
            "WEB_APP_URL을 실제 배포 주소로 바꾸세요."
        )


def main():
    validate_settings()
    clear_leds()

    while True:
        cycle_started = time.ticks_ms()

        try:
            average_value = read_average()
            grade = value_to_grade(average_value)
            led_count = GRADE_LED_COUNTS[grade]

            show_grade(grade)

            print("--------------------------------")
            print("평균 ADC:", average_value)
            print("상대등급:", grade)
            print("켜진 LED 개수:", led_count)

            if connect_wifi():
                status_code, response_body = send_value(
                    average_value,
                    grade,
                    led_count
                )

                http_ok = (
                    status_code >= 200
                    and status_code < 300
                )

                app_ok = (
                    response_body.find(
                        '"success":true'
                    ) >= 0
                )

                if http_ok and app_ok:
                    print("구글 시트 기록 성공")
                else:
                    print("구글 시트 기록 실패")
                    print("HTTP 상태:", status_code)
                    print(
                        "응답 본문:",
                        response_body
                    )
            else:
                print(
                    "Wi-Fi 연결 실패로 전송을 건너뜁니다."
                )

        except Exception as error:
            print("실행 오류:", repr(error))

        finally:
            gc.collect()

        elapsed_ms = time.ticks_diff(
            time.ticks_ms(),
            cycle_started
        )

        remaining_ms = (
            INTERVAL * 1000
            - elapsed_ms
        )

        if remaining_ms > 0:
            time.sleep_ms(remaining_ms)


main()

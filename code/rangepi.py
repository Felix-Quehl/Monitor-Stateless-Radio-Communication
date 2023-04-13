import utime
from machine import UART,SPI
from machine import Pin
import st7789
import time
import math
import random

import sys
import uselect

import vga1_8x16 as font1
#import vga2_8x8 as font
import vga1_16x32 as font
import vga1_16x16 as font2

spi = SPI(1, baudrate=40000000, sck=Pin(10), mosi=Pin(11))
tft = st7789.ST7789(spi,135,240,reset=Pin(12, Pin.OUT),cs=Pin(9, Pin.OUT),dc=Pin(8, Pin.OUT),backlight=Pin(13, Pin.OUT),rotation=1)
tft.init()

Mode0 = machine.Pin(2, machine.Pin.OUT)
Mode1 = machine.Pin(3, machine.Pin.OUT)

Mode0.value(0)
Mode1.value(0)

lora = UART(0,baudrate = 9600,tx = Pin(0),rx = Pin(1))

spoll=uselect.poll()     
spoll.register(sys.stdin, uselect.POLLIN)

loop_time = 0

uplink_last = 0
uplink_status = False
uplink_vector = random.randint(0, 100)

downlink_last = 0
downlink_status = False
downlink_vector = 0

CLOCK_HEADER = "VC"
SYNC_SHORT_THRESHOLD = 15000
SYNC_LONG_THRESHOLD = 60000

debug = 0


def prompt_com(origin, msg):
    if debug:
        print(f'{loop_time}\t:\t{origin}\t:\t{msg}')


def prompt_display(msg, row, color):
    tft.text(font1, msg,  0, 18 * row, color)


def get_inbox():
    msg = ''
    if lora.any():
        msg = lora.read()
        msg = msg.strip().decode("utf-8") 
    if len(msg) == 0:
        msg = None
    else:
        prompt_com('lora-receive-okay', msg)
        prompt_display(f"RX:{msg}", 5, st7789.GREEN)
    return msg
    
    
def get_input():
    msg = ''
    if spoll.poll(0):
        msg = sys.stdin.readline() 
        msg = msg.strip()
    if len(msg) == 0:
        msg = None
    return msg
    
    
def outbox(msg):
    lora.write(msg)
    prompt_com('lora-transmit-okay', msg)
    prompt_display(f"TX:{msg}", 6, st7789.CYAN)


def handle_clock_receive(inbox):
    global downlink_last
    global downlink_status
    global downlink_vector
    global uplink_status
    
    inbox_string = inbox
    inbox_parts = inbox_string.split(':')
    if len(inbox_parts) == 3:
        downlink_vector_new = int(inbox_parts[1])
        downlink_vector_diff = downlink_vector_new - downlink_vector
        if downlink_vector_diff == 1:
            downlink_status = True
        else:
            downlink_status = False
        
        uplink_vector_ack = int(inbox_parts[2])
        uplink_vector_match = uplink_vector_ack == uplink_vector
        if uplink_vector_match:
            uplink_status = True
        else:
            uplink_status = False
            
        downlink_vector = downlink_vector_new
        downlink_last = loop_time;

    
def handle_clock_transmit():
    global downlink_status
    global uplink_status
    global uplink_last
    global uplink_vector
    
    since_uplink = loop_time - uplink_last
    since_downlink = loop_time - downlink_last
    if since_downlink > (SYNC_LONG_THRESHOLD * 1.5):
        downlink_status = False
        uplink_status = False
        
    long_time_since_activity = since_uplink > SYNC_LONG_THRESHOLD
    link_not_established = not downlink_status or not uplink_status
    tx_threshold_okay = since_uplink > SYNC_SHORT_THRESHOLD
    link_attempt = link_not_established and tx_threshold_okay
            
    if link_attempt or long_time_since_activity:
        uplink_vector = uplink_vector + 1
        message = f'{CLOCK_HEADER}:{uplink_vector}:{downlink_vector}'
        outbox(message)
        uplink_last = loop_time
        
        
def display_status():
    
    if downlink_status:
        prompt_display(f"TX-MATCH: {uplink_vector}", 0, st7789.GREEN)
    else:
        prompt_display(f"TX-ERROR: {uplink_vector}", 0, st7789.RED)
        
    if uplink_status:
        prompt_display(f"RX-MATCH: {downlink_vector}", 1, st7789.GREEN)
    else:
        prompt_display(f"RX-ERROR: {downlink_vector}", 1, st7789.RED)
        
    if uplink_status and downlink_status:
        prompt_display("P2P-LINK: OKAY", 2, st7789.GREEN)
    else:
        prompt_display("P2P-LINK: LOST", 2, st7789.RED)


def handle_transactions():
    
    handle_clock_transmit()
    
    inbox = get_inbox()
    if inbox:
        if inbox.startswith(CLOCK_HEADER):
            handle_clock_receive(inbox)
        else:
            print(inbox)
            
    user_input = get_input()
    if user_input:
        outbox(user_input)
    


def loop():
    global loop_time
    while True:
        loop_time = utime.ticks_ms()
        handle_transactions()
        display_status()

loop()



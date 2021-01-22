import os
import json
from rich import print
from multiprocessing import Queue
from typing import Callable, List
from paho.mqtt import client as paho_mqtt_client

# MQTT topics
MQTT_TOPIC_HELLO = "hello"
MQTT_TOPIC_STATS = "receive-from-jetson"
MQTT_TOPIC_ALERTS = "alerts"
MQTT_TOPIC_FILES = "video-files"
MQTT_TOPIC_COMMANDS = "commands"

# MQTT commands to device
MQTT_CMD_FILE_SAVE = "save_file"
MQTT_CMD_STREAMING_START = "streaming_start"
MQTT_CMD_STREAMING_STOP = "streaming_stop"
MQTT_CMD_INFERENCE_RESTART = "inference_restart"

# Must come defined as environment var or MQTT gets disabled
MQTT_BROKER_IP = os.environ.get("MQTT_BROKER_IP", None)
MQTT_DEVICE_NAME = os.environ.get("MQTT_DEVICE_NAME", None)
MQTT_BROKER_PORT = 1883
MQTT_DEVICE_DESCRIPTION = "MaskCam @ Jetson Nano"

mqtt_msg_queue = Queue(maxsize=100)  # 100 mqtt messages stored max


def mqtt_send_queue(mqtt_client):
    success = True
    while not mqtt_msg_queue.empty() and success:
        q_msg = mqtt_msg_queue.get_nowait()
        print(f"Sending enqueued message to topic: {q_msg['topic']}")
        success = mqtt_send_msg(mqtt_client, q_msg["topic"], q_msg["message"])
    return success


def mqtt_connect_broker(
    client_id: str,
    broker_ip: str,
    broker_port: int,
    subscribe_to: List[List] = None,
    cb_success: Callable = None,
) -> paho_mqtt_client:
    def cb_on_connect(client, userdata, flags, code):
        if code == 0:
            print("[green]Connected to MQTT Broker[/green]")
            if subscribe_to:
                print("Subscribing to topics:")
                print(subscribe_to)
                client.subscribe(subscribe_to)  # Always re-suscribe after reconnecting
            if cb_success is not None:
                cb_success(client)
            if not mqtt_send_queue(client):
                print(f"[red]Failed to send MQTT message queue after connecting[/red]")
        else:
            print(f"[red]Failed to connect to MQTT[/red], return code {code}\n")

    def cb_on_disconnect(client, userdata, code):
        print(f"Disconnected from MQTT Broker, code: {code}")

    client = paho_mqtt_client.Client(client_id)
    client.on_connect = cb_on_connect
    client.on_disconnect = cb_on_disconnect
    client.connect(broker_ip, broker_port)
    client.loop_start()
    return client


def mqtt_send_msg(mqtt_client, topic, message, enqueue=True):
    if mqtt_client is None:
        print(f"Skipping MQTT message to topic: {topic}")
        return False

    # Check previous enqueued msgs
    mqtt_send_queue(mqtt_client)

    result = mqtt_client.publish(topic, json.dumps(message))
    if result[0] == 0:
        print(f"{topic} | MQTT message [green]SENT[/green]")
        print(message)
        return True
    else:
        if enqueue:
            if not mqtt_msg_queue.full():
                print(f"{topic} | MQTT message [yellow]ENQUEUED[/yellow]")
                mqtt_msg_queue.put_nowait({"topic": topic, "message": message})
            else:
                print(f"{topic} | MQTT message [red]DROPPED: FULL QUEUE[/red]")
        else:
            print(f"{topic} | MQTT message [yellow]DISCARDED[/yellow]")
        return False

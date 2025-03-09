import pika
import json
import time

def callback(ch, method, properties, body):
    """ Modtager og processer beskeder fra RabbitMQ """
    email_data = json.loads(body)
    print(f"📥 Received email: {email_data['email_id']} - Processing...")

    time.sleep(2)  # Simulerer behandlingstid
    print(f"✅ Done processing {email_data['email_id']}")

    ch.basic_ack(delivery_tag=method.delivery_tag)  # Bekræft besked

def start_indexer():
    """ Starter indexer og forbinder til RabbitMQ """
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
    channel = connection.channel()
    channel.queue_declare(queue="email_queue", durable=True)
    channel.basic_consume(queue="email_queue", on_message_callback=callback)

    print("🎧 Indexer is waiting for messages...")
    channel.start_consuming()

if __name__ == "__main__":
    start_indexer()

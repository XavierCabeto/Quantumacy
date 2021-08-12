import socket
import select
import sys
import re
import logging
from node import Node
from models import Photon
from qexceptions import qsocketerror, qobjecterror

logging.basicConfig(level=logging.DEBUG)


class receiver(Node):
    """Receiver class, it expands node, it contains methods to communicate a sender node, it can't take action but it
    has to wait for the sender node for sending data, it can answer to a request with a message or to a message with an
    acknowledgement"""
    def __init__(self, ID, token, size):
        super().__init__(ID, token, size)
        self.polarization_vector = []
        self.sent_acks = []
        self.sent_messages = {}

    def measure_photon_pulse(self):
        """Measure photon pulse

        given the vector that stores polarizations of received photons it creates a list of photons each polarization,
        basis and bit will be determined byt the measure method according to physical properties, a list with the basis
        of every photon will be stored
        """
        for p in range(len(self.polarization_vector)):
            self.photon_pulse.append(Photon())
            self.photon_pulse[p].polarization = self.photon_pulse[p].measure(int(self.polarization_vector[p]))
            self.photon_pulse[p].bit = self.photon_pulse[p].set_bit_from_measurement()
        self.basis = [p.basis for p in self.photon_pulse]

    def listen_quantum(self):
        """ Listen method to receive photon pulse

         it behaves like a wrapper for recv for photon pulses
        """
        try:
            logging.info("listening to quantum channel for photon pulse...")
            while True:
                message = self.recv('qpulse')
                self.polarization_vector = message.split("~")[:-1]
                break
        except socket.error:
            raise qsocketerror("not connected to any channel")

    def recv(self, header: str) -> str:
        """Receive function for receiver node

        it listen for a message, in case the header of the received message doesn't match it checks if an acknowledgment
        for the received message has been already sent or if the received message is an acknowledgement itself for a
        previously sent message, it sends a new acknowledgment in the first case and it sends again the message in the
        other case, if the message is new and the header is correct it sends an acknowledgement and it saves it
        Args:
            header (str): unique identifier of the message that has to be received
        Returns:
            message (str): the payload of the received data, the header and some other infos are not returned
        """
        try:
            for i in range(self.connection_attempts):  # loop for different messages
                message = ''
                while True:  # loop for different parts of the same message (len > buff_size)
                    ready = select.select([self.socket], [], [], self.timeout_in_seconds)
                    if ready[0]:
                        data_recv = self.socket.recv(self.buffer_size).decode()
                        message += re.sub(self.regex, '', data_recv)  # removing ('xxx.xxx.xxx.xxx', xxxxx):
                        if message.count(':') >= 2:  # checking if payload started and finished
                            mess_list = message.split(':')[:2]
                            break
                label = mess_list[0]
                if label != header and label in self.sent_acks:
                    self.socket.send((label + ":ack:").encode())
                    continue
                elif label != header and label in self.sent_messages:
                    self.socket.send((label + ":" + self.sent_messages[label] + ':').encode())
                    continue
                self.socket.send((header + ":ack:").encode())
                self.sent_acks.append(label)
                dec_message = self.decrypt_not_qpulse(label, mess_list[1])
                logging.info("Received: " + label + ":" + dec_message)
                return dec_message
        except Exception as err:
            logging.error('Bob failed to receive {0}:\n{1}'.format(header, str(err)))
            sys.exit()
        except ConnectionError:
            logging.error("Bob failed to receive")
            sys.exit()

    def send(self, header: str, message: str):
        """ Send method for receiver

        it listens for the request from the sender node, in case the header of the received message doesn't match it
        checks if an acknowledgment for the received header has been already sent or if the message for the requested
        header has been already sent, it sends a new acknowledgement in the first case and it sends again the message in
        the other case, it sends the expected message if the header is correct, the sent message is saved in a list
        Args:
            header (str): unique identifier
            message (str): message
        """
        try:
            for i in range(self.connection_attempts):
                ready = select.select([self.socket], [], [], self.timeout_in_seconds)
                if ready[0]:
                    data = self.socket.recv(self.buffer_size)
                request = data.decode().split(':')
                label = request[1]
                if label != header and label in self.sent_acks:
                    self.socket.send((label + ':ack:').encode())
                    logging.info("Sent: " + header + ':ack:')
                    continue
                elif label != header and label in self.sent_messages:
                    self.socket.send((label + ':' + self.sent_messages[label] + ':').encode())
                    logging.info("Sent: " + header + ':' + self.sent_messages[label] + ':')
                    continue
                data = self.encrypt_not_qpulse(header, message)
                self.socket.send(data.encode())
                logging.info('Sent: ' + header + ':' + message)
                self.sent_messages[header] = data
                return True
        except ConnectionError as ce:
            logging.error('Bob failed to send {0}:\n{1}'.format(header, str(ce)))
            sys.exit()

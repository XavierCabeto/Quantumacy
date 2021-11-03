# -*- coding: utf-8 -*-
"""
Created on Wed May 12 21:57:13 2021

@author: Alberto Di Meglio
"""

import os
import sys
import json
import logging
import uvicorn
from base64 import urlsafe_b64encode
from fastapi import FastAPI
from QKDSimkit.QKDSimClients.sender import sender
from QKDSimkit.QKDSimChannels.qexceptions import qsocketerror, qobjecterror
from pydantic import BaseModel
from cryptography.fernet import Fernet
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.ERROR)

app = FastAPI()


def import_key(channel_address: str, ID: str, size: int = 256):

    channelIP, channelPort = channel_address.split(':')
    channelPort = int(channelPort)

    # clean up
    _ = os.system('clear')

    for count in range(0, 1000):
        alice = sender(ID, size)
        try:
            # connect to quantum channel
            alice.connect_to_channel(channelIP, channelPort)
            # create and send a photon pulse through the quantum channel
            photon_pulse = alice.create_photon_pulse()
            alice.send_photon_pulse(photon_pulse)

        except qsocketerror as err:
            logging.error(
                "An error occurred while connecting to the quantum channel (" + str(err) + "). Disconnecting.")
            sys.exit()
        except Exception as e:
            logging.error("An error occurred. Disconnecting.\n" + str(e))
            sys.exit()

        # connect to classic channel
        try:
            alice.reset_socket()
            alice.connect_to_channel(channelIP, channelPort)
        except qsocketerror as err:
            logging.error(
                "An error occurred while connecting to the classic channel (" + str(err) + "). Disconnecting.")
            sys.exit()
        except Exception as err:
            logging.error("An error occurred (" + str(err) + "). Disconnecting.")
            sys.exit()

        # exchange basis
        try:
            # listen for Bob's basis
            alice.listen_for('bob', 'other_basis')
            # generate the reconciled key from Bob's basis
            alice.generate_reconciled_key()
            # create and send the basis through the classic channel
            alice.send('alice-reconciled_key', repr(alice.reconciled_key))

        except qsocketerror as err:
            logging.error(
                "An error occurred while connecting to the classic channel (" + str(err) + "). Disconnecting.")
            sys.exit()
        except Exception as err:
            logging.error("An error occurred (" + str(err) + "). Disconnecting.")
            sys.exit()

        # create key and public sub key
        alice.create_keys()

        # exchange sub key
        try:
            # send the public sub key
            alice.send('alice-other_sub_key', repr(alice.sub_shared_key))
            # listen for Bob's public sub key
            alice.listen_for('bob', 'other_sub_key')

            alice.decision = alice.validate()

            # send decision
            alice.send('alice-other_decision', repr(alice.decision))
            # listen for Alice's sub key
            alice.listen_for('bob', 'other_decision')
        except qsocketerror as err:
            logging.error(
                "An error occurred while connecting to the classic channel (" + str(err) + "). Disconnecting.")
            sys.exit()
        except Exception as err:
            logging.error("An error occurred (" + str(err) + "). Disconnecting.")
            sys.exit()

        alice.reset_socket()

        # choose what to do
        if alice.decision == alice.other_decision and alice.decision == 1:
            # return a correct key
            alice.get_key()
            logging.info("Success!")
            alice.key = alice.key[:size]
            alice.key = [int("".join(map(str, alice.key[i:i + 8])), 2) for i in range(0, len(alice.key), 8)]
            return urlsafe_b64encode(bytearray(alice.key))
        elif alice.decision == alice.other_decision and alice.decision == 0:
            # retry
            logging.info("Failed to match key, trying again")
            continue
        else:
            # exit
            logging.warning("Failed! Noise or eavesdropper detected")
            return -1
    logging.warning("Error: too many attempts to find a shared key")
    return -1


class qkdParams(BaseModel):
    number: int = 1
    size: int = 256
    ID: str = 'id'


@app.get("/test")
async def root(number: int = 1, size: int = 256, ID: str = 'id'):
    answer = {}
    keys = []
    s = json.load(open('../config.json', ))['channel']
    address = '{}:{}'.format(s['host'], s['port'])
    for i in range( number):
        key = import_key(channel_address=address, ID=ID, size=size)
        keys.append({"key_ID": i, "key": key})
    answer["keys"] = keys
    return answer


@app.post("/test")
async def root(qkdParams: qkdParams):
    answer = {}
    keys = []
    s = json.load(open('../config.json', ))['channel']
    address = '{}:{}'.format(s['host'], s['port'])
    for i in range(qkdParams.number):
        key = import_key(channel_address=address, ID=qkdParams.ID, size=qkdParams.size)
        keys.append({"key_ID": i, "key": key})
    answer["keys"] = keys
    return answer


origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == '__main__':
    #TODO: fix this to provide different options and update token management

    uvicorn.run('QKD_Alice:app', port=5001)

    '''
    a = import_key('id', b'7KHuKtJ1ZsV21DknPbcsOZIXfmH1_MnKdOIGymsQ5aA=', 256)
    f = Fernet(a)
    f.encrypt(b'ciao')'''
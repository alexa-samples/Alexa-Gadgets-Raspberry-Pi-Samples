#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#
import logging.config
import subprocess
import sys

logger = logging.getLogger(__name__)

"""
Execute shell commands using subprocess and log based on the logging level
"""
def subprocess_run_and_log(command):
    output = subprocess.check_output(command, shell=True)
    logger.debug(output.decode('ascii'))

"""
Log payload bytes
"""
def log_bytes(payload):
    payload = bytearray(payload)
    printable_list = '[' + ', '.join('0x' + '%02x' % i for i in payload) + ']'
    logger.debug(printable_list)
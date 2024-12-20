#!/bin/bash
apt-get update && apt-get install -y locales
locale-gen pt_BR.UTF-8
export LANG=pt_BR.UTF-8
export LC_ALL=pt_BR.UTF-8

# Comando para iniciar sua aplicação
gunicorn app:server
#!/bin/bash

# Adicionar suporte ao locale pt_BR.UTF-8
echo "Configurando locale pt_BR.UTF-8..."
export LANG=pt_BR.UTF-8
export LC_ALL=pt_BR.UTF-8

# Garantir que o ambiente esteja configurado corretamente
locale-gen pt_BR.UTF-8
dpkg-reconfigure locales

# Iniciar a aplicação
gunicorn app:server
#!/bin/bash
# Setup do Monitor de Emendas — Paulo Azi
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo ""
echo "========================================================"
echo "  Monitor de Emendas Parlamentares — Paulo Azi"
echo "========================================================"
echo ""

# Verificar Python 3.9+
if ! command -v python3 &>/dev/null; then
  echo "ERRO: Python 3 não encontrado. Instale em python.org"
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python $PYTHON_VERSION encontrado."

# Criar ambiente virtual
if [ ! -d ".venv" ]; then
  echo "Criando ambiente virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Instalando dependências..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Criar .env se não existir
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "ATENÇÃO: Arquivo .env criado a partir do exemplo."
  echo "Edite o arquivo .env com suas credenciais antes de continuar."
  echo "  - TRANSPARENCIA_API_KEY: solicite em api.portaldatransparencia.gov.br"
  echo "  - EMAIL_REMETENTE, EMAIL_SENHA: configure sua conta de e-mail"
  echo "  - EMAIL_DESTINATARIOS: e-mails que receberão os relatórios"
  echo ""
  echo "Após configurar o .env, execute:"
  echo "  source .venv/bin/activate"
  echo "  python main.py historico   # coleta os últimos 8 anos (pode demorar)"
  echo "  python main.py relatorio --local  # testa gerando HTML local"
  echo "  python main.py monitor     # inicia o daemon contínuo"
  echo ""
else
  echo ".env já configurado."
  echo ""
  echo "Comandos disponíveis (ative o venv primeiro: source .venv/bin/activate):"
  echo "  python main.py historico        — coleta histórico 8 anos"
  echo "  python main.py coletar          — atualização incremental"
  echo "  python main.py relatorio --local — gera HTML local para revisão"
  echo "  python main.py relatorio        — envia por e-mail"
  echo "  python main.py resumo           — exibe resumo no terminal"
  echo "  python main.py monitor          — daemon contínuo"
fi

echo "========================================================"

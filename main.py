#!/usr/bin/env python3

# Bibliotecas PyPIP
import ftplib
import git
import os
from time import sleep
from signal import signal, SIGINT
# Arquivo local de parâmetros
import PARAMS

# Constantes de ambiente
BASE_GIT_URL = "https://github.com/"
LOCAL_REPO_PATH = "./REPO/"
# Variáveis auxiliares
PASTA_REMOTA_ATUAL = ''
server = ftplib.FTP
ARQS_IGNORAR = [
    'main.py',
    'PARAMS.py',
    '.git'
]


def handleFimDePrograma(sig, frame):
    """
    Fecha conexão com servidor e termina execução do programa
    """
    print("\n\nFechando servidor e terminando execução...")
    server.close(server)
    exit(0)


def cdRemoto(server: ftplib.FTP,
             path: str) -> None:
    server.cwd(path)
    PASTA_REMOTA_ATUAL = server.pwd()


def testaConexao(server: ftplib.FTP) -> None:
    """
    Teste conexão FTP e loga novamente se necessário
    """
    try:
        # Teste de conexão
        server.getwelcome()
    except Exception:
        # Reconecta e reloga
        server.connect(PARAMS.IP_SERVIDOR, port=22)
        server.login(user=PARAMS.LOGIN_SERVIDOR,
                     passwd=PARAMS.SENHA_SERVIDOR)
        # Volta para última localização conhecida no servidor
        server.cwd(PASTA_REMOTA_ATUAL)


def carregaDiferencas(repo: git.Repo,
                      server: ftplib.FTP) -> bool:
    testaConexao(server)

    # Pega última versão do repositório
    repo.remotes.origin.fetch()
    # Confere diferença entre última versão e repositório local
    diffs = repo.git.diff("..origin", name_only=True).split('\n')

    # Atualiza repositório local
    repo.remotes.origin.pull()

    # Loop entre cada arquivo alterado
    for diff in diffs:
        testaConexao(server)

        # Confere arquivo válido
        if len(diff) <= 0 or diff in ARQS_IGNORAR:
            continue

        # Exibe arquivo a ser atualizado e salva seu path
        print("Atualizando arquivo: '{}'".format(diff))
        pathArq = LOCAL_REPO_PATH + diff

        # Entra no diretório correto criando pastas necessárias
        pathComps = diff.split('/')
        for i in range(0, len(pathComps) - 1):
            # Tenta criar subdiretório
            try:
                server.mkd(pathComps[i])
            # Único erro válido na criação como pasta já existente
            except Exception as e:
                if str(e).split()[0] != '550':
                    print("Erro na criação de pasta!")
                    print(e)
                    exit(1)
            # "Caminha" pelos subdiretórios
            cdRemoto(server, pathComps[i])

        # Caso arquivo exista, alteração foi modificação não remoção, assim
        # tranfere novo arquivo/versão
        if os.path.exists(pathArq):
            with open(pathArq, "rb") as arq:
                server.storbinary("STOR " + pathComps[-1], arq)
        # Caso contrário, deleta arquivo
        else:
            server.delete(pathComps[-1])

        # Volta para diretório base
        for i in range(0, len(pathComps) - 1):
            cdRemoto(server, '..')


def copiaPastaFTP(server: ftplib.FTP,
                  folder: str) -> bool:
    """
    Copia pasta inteira recursivamente para servidor
    (usada na cópia inicial)
    """
    testaConexao(server)

    # Para cada entrada no diretório atual
    for entry in os.listdir("./" + folder):
        # Confere que arquivo não seja hidden
        if entry in ARQS_IGNORAR:
            continue
        # Caso seja diretório
        if os.path.isdir(folder + entry):
            # Tenta criar diretório no servidor
            try:
                server.mkd(entry)
            # Apenas aceita erro caso já criado
            except Exception as e:
                if str(e).split()[0] != '550':
                    print("Erro na criação de pasta!")
                    print(e)
                    exit(1)
            # Entra na pasta criada
            cdRemoto(server, entry)
            # Chama recursivamente para entradas do novo diretório
            copiaPastaFTP(server, folder + entry + '/')
            # Retorna para diretório pai
            cdRemoto(server, '..')
        # Caso seja arquivo
        else:
            # Escreve arquivo para servidor
            pathArq = folder + entry
            with open(pathArq, "rb") as arq:
                server.storbinary("STOR " + entry, arq)


def main():
    # Cria e testa conecão FTP
    try:
        server = ftplib.FTP()
        testaConexao(server)
    except Exception:
        print("Erro na conexão (S)FTP! Cheque as credenciais e endereço "
              "no arquivo de parâmetros e tente novamente...")
        exit(1)

    # Entre no diretório base
    cdRemoto(server, PARAMS.DIRETORIO_BASE_FTP)
    # Exibe diretório base
    print("Diretório FTP base:")
    print(server.dir(), '\n')

    # Clona repositório local
    if not os.path.exists(LOCAL_REPO_PATH):
        print("Criando cópia local do repo...")
        localRepo = git.Repo.clone_from(BASE_GIT_URL +
                                        PARAMS.REPOSITORIO_GITHUB,
                                        to_path=LOCAL_REPO_PATH)
    # Vincula repositório local caso já clonado, atualizando-o
    else:
        print("Vinculando repositório local..")
        localRepo = git.Repo(LOCAL_REPO_PATH)
        localRepo.remotes.origin.pull()

    # Envia arquivos inicialmente para o FTP.......
    print("Copiando estado inicial para servidor FTP...")
    copiaPastaFTP(server, "")

    # Entra em loop conferindo alterações (com  delay pré definido)
    print("Entrando em loop de conferência...")
    while True:
        carregaDiferencas(localRepo, server)
        sleep(PARAMS.MINS_DELAY*60)


if __name__ == "__main__":
    signal(SIGINT, handleFimDePrograma)
    main()

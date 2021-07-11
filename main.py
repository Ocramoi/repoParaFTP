#!/usr/bin/env python3

# Bibliotecas PyPIP
# import ftplib
import git
import os
from time import sleep
from signal import signal, SIGINT
import paramiko
# Arquivo local de parâmetros
import PARAMS

# Constantes de ambiente
BASE_GIT_URL = "https://github.com/"
LOCAL_REPO_PATH = "./REPO/"
# Variáveis auxiliares
PASTA_REMOTA_ATUAL = ''
# server = ftplib.FTP
transport = paramiko.Transport
server = paramiko.SFTPClient


def handleFimDePrograma(sig, frame):
    """
    Fecha conexão com servidor e termina execução do programa
    """
    print("\n\nFechando servidor e terminando execução...")
    try:
        server.close(server)
        transport.close(transport)
    except Exception:
        pass
    exit(0)


def cdRemoto(server: paramiko.SFTPClient,
             path: str) -> None:
    # server.cwd(path)
    server.chdir(path)
    # PASTA_REMOTA_ATUAL = server.pwd()
    PASTA_REMOTA_ATUAL = server.getcwd()


def testaConexao(server: paramiko.SFTPClient) -> None:
    """
    Teste conexão FTP e loga novamente se necessário
    """
    try:
        # Teste de conexão
        server.getcwd()
    except Exception:
        # Reconecta e reloga
        transport = paramiko.Transport(
            (PARAMS.IP_SERVIDOR, PARAMS.PORTA_SERVIDOR)
        )
        transport.connect(None,
                          username=PARAMS.LOGIN_SERVIDOR,
                          assword=PARAMS.SENHA_SERVIDOR)
        server = paramiko.SFTPClient.from_transport(transport)
        # Volta para última localização conhecida no servidor
        server.chdir(PASTA_REMOTA_ATUAL)


def carregaDiferencas(repo: git.Repo,
                      server: paramiko.SFTPClient) -> bool:
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
        if len(diff) <= 0 or diff in PARAMS.ARQS_IGNORAR:
            continue

        # Exibe arquivo a ser atualizado e salva seu path
        print("Atualizando arquivo: '{}'".format(diff))
        pathArq = LOCAL_REPO_PATH + diff

        # Entra no diretório correto criando pastas necessárias
        pathComps = diff.split('/')
        tamSub = len(pathComps) - 1
        for i in range(0, len(pathComps) - 1):
            # Tenta criar subdiretório
            try:
                server.mkdir(pathComps[i])
            # Único erro válido na criação como pasta já existente
            except Exception:
                pass
            # "Caminha" pelos subdiretórios
            cdRemoto(server, pathComps[i])

        # Caso arquivo exista, alteração foi modificação não remoção, assim
        # tranfere novo arquivo/versão
        if os.path.exists(pathArq):
            server.put(pathArq, pathComps[-1])
        # Caso contrário, deleta arquivo
        else:
            server.remove(pathComps[-1])

        if len(server.listdir()) == 0:
            cdRemoto(server, '..')
            server.rmdir(pathComps[tamSub - 1])
            tamSub -= 1

        # Volta para diretório base
        for i in range(tamSub):
            cdRemoto(server, '..')


def copiaPastaFTP(server: paramiko.SFTPClient,
                  folder: str) -> bool:
    """
    Copia pasta inteira recursivamente para servidor
    (usada na cópia inicial)
    """
    testaConexao(server)

    # Para cada entrada no diretório atual
    for entry in os.listdir("./" + folder):
        # Confere que arquivo não deve ser ignorado
        if entry in PARAMS.ARQS_IGNORAR:
            continue
        # Caso seja diretório
        if os.path.isdir(folder + entry):
            # Tenta criar diretório no servidor
            try:
                # server.mkd(entry)
                server.mkdir(entry)
            # Apenas aceita erro caso já criado
            except Exception:
                pass
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
            server.put(pathArq, entry)


def main():
    # Cria e testa conecão SFTP
    try:
        transport = paramiko.Transport(
            (PARAMS.IP_SERVIDOR, PARAMS.PORTA_SERVIDOR)
        )
        transport.connect(None,
                          username=PARAMS.LOGIN_SERVIDOR,
                          password=PARAMS.SENHA_SERVIDOR)
        server = paramiko.SFTPClient.from_transport(transport)
    except Exception as e:
        print("Erro na conexão (S)FTP! Cheque as credenciais e endereço "
              "no arquivo de parâmetros e tente novamente...")
        print("Informações de erro: \n", e)
        exit(1)

    # Entre no diretório base
    cdRemoto(server, PARAMS.DIRETORIO_BASE_FTP)
    # Exibe diretório base
    print("Diretório FTP base:")
    # print(server.dir(), '\n')
    print(server.listdir(), '\n')

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
    copiaPastaFTP(server, LOCAL_REPO_PATH)

    # Entra em loop conferindo alterações (com  delay pré definido)
    print("Entrando em loop de conferência...")
    while True:
        carregaDiferencas(localRepo, server)
        sleep(PARAMS.MINS_DELAY*60)


if __name__ == "__main__":
    signal(SIGINT, handleFimDePrograma)
    main()

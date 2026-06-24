import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Plataforma de Assinaturas", page_icon="🖋️", layout="wide")

# --- MEMÓRIA DO SISTEMA DE SESSÃO ---
if "banco_dados" not in st.session_state:
    st.session_state.banco_dados = {
        "caminho_original": None,
        "conteudo_original": None,
        "hash_seguranca": None,
        "assinantes": []
    }

def obter_tabela_historico():
    if not st.session_state.banco_dados["assinantes"]:
        return []
    dados_tabela = []
    for a in st.session_state.banco_dados["assinantes"]:
        dados_tabela.append({
            "Nome": a["nome"],
            "E-mail": a["email"],
            "Status": a["status"],
            "CPF Utilizado": a["cpf"],
            "Data/Hora": a["data"]
        })
    return dados_tabela

# --- MOTOR DE DISPARO REAL (PORTA 465 SSL) ---
def enviar_email_individual(meu_email, minha_senha_app, email_destino, nome_assinante, link_assinatura):
    try:
        servidor_smtp = "smtp.gmail.com"
        porta = 465
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = email_destino
        msg['Subject'] = "Assinatura Pendente - Plataforma Digital"
        
        # Texto do e-mail atualizado com as novas instruções de obrigatoriedade
        corpo = f"""Olá, {nome_assinante}.

Você foi incluído como assinante de um documento oficial em nossa plataforma.

⚠️ INSTRUÇÕES IMPORTANTES PARA A ASSINATURA:
1. Confira a grafia do seu nome para a assinatura: {nome_assinante}
2. Acesse a plataforma pelo link seguro abaixo.
3. Na aba 'Página do Assinante', você deverá digitar obrigatoriamente o seu NOME COMPLETO (exatamente com a grafia acima) e o seu CPF para validar o documento.

Link de acesso seguro:
{link_assinatura}
"""
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        servidor = smtplib.SMTP_SSL(servidor_smtp, porta)
        servidor.login(meu_email, minha_senha_app)
        servidor.sendmail(meu_email, email_destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- PROCESSAR ENTRADA DE LOTE ---
def criador_processa_lote(arquivo_pdf, texto_assinantes, meu_email, minha_senha_app, link_sistema):
    if arquivo_pdf is None:
        return st.error("ERRO: Anexe um arquivo PDF.")
    if not texto_assinantes.strip():
        return st.error("ERRO: Insira pelo menos 1 assinante.")
    if not meu_email or not minha_senha_app:
        return st.error("ERRO: Configure suas credenciais de e-mail.")
    if not link_sistema.strip():
        return st.error("ERRO: Insira o link do seu sistema para enviar aos assinantes.")

    st.session_state.banco_dados["caminho_original"] = arquivo_pdf.name
    st.session_state.banco_dados["conteudo_original"] = arquivo_pdf.getvalue()
    st.session_state.banco_dados["assinantes"] = []
    
    hasher = hashlib.sha256()
    hasher.update(st.session_state.banco_dados["conteudo_original"])
    st.session_state.banco_dados["hash_seguranca"] = hasher.hexdigest()

    linhas = texto_assinantes.strip().split("\n")
    emails_enviados = 0
    linhas_ignoradas = 0
    
    for linha in linhas:
        if ";" in linha:
            partes = linha.split(";")
            nome = partes[0].strip()
            email = partes[1].strip()
            token = secrets.token_hex(4)
            
            st.session_state.banco_dados["assinantes"].append({
                "nome": nome, "email": email, "token": token,
                "cpf": "", "status": "Pendente", "data": "-"
            })
            
            sucesso = enviar_email_individual(meu_email, minha_senha_app, email, nome, link_sistema)
            if sucesso:
                emails_enviados += 1
        else:
            linhas_ignoradas += 1

    total_cadastrados = len(st.session_state.banco_dados["assinantes"])
    relatorio = f"""=== LOTE PROCESSADO ===
1. Hash SHA-256: {st.session_state.banco_dados['hash_seguranca']}
2. Disparos: {emails_enviados} e-mails enviados com sucesso.
3. Linhas ignoradas: {linhas_ignoradas}
4. Total na memória: {total_cadastrados} assinantes cadastrados."""
    
    st.session_state.relatorio_envio = relatorio
    st.success("Lote disparado com sucesso!")

# --- INTERFACE VISUAL ---
st.title("🖋️ Plataforma de Assinatura Digital (Até 40 Assinantes)")

aba1, aba2, aba3 = st.tabs(["Painel do Criador", "Página do Assinante", "Histórico do Lote"])

with aba1:
    col1, col2 = st.columns(2)
    with col1:
        campo_meu_email = st.text_input("Seu Gmail de Envio", placeholder="seu_email@gmail.com")
        campo_minha_senha = st.text_input("Sua Senha de App do Gmail (16 letras)", type="password")
        campo_link_sistema = st.text_input("Link do seu Sistema (Copie da barra de endereços)", placeholder="https://seu-app.streamlit.app")
        campo_arquivo = st.file_uploader("Arraste o PDF do Contrato", type=["pdf"])
        campo_lote = st.text_area(
            "Lista de Assinantes (Formato: Nome; E-mail)", 
            placeholder="João Silva; joao@email.com\nCarlos Roberto; carlos@email.com",
            height=150
        )
        if st.button("🚀 Disparar E-mails para o Lote", type="primary"):
            criador_processa_lote(campo_arquivo, campo_lote, campo_meu_email, campo_minha_senha, campo_link_sistema)
            st.rerun()
            
    with col2:
        st.subheader("Painel de Controle")
        if "relatorio_envio" in st.session_state:
            st.text_area("Relatório de Saída", st.session_state.relatorio_envio, height=250)
        else:
            st.info("Aguardando o envio do primeiro lote...")

with aba2:
    col3, col4 = st.columns(2)
    with col3:
        campo_nome_cliente = st.text_input("Nome Completo do Assinante (Idêntico ao recebido por e-mail)")
        campo_cpf_cliente = st.text_input("Digite seu CPF para assinar")
        
        if st.button("✍️ Confirmar Assinatura Digital"):
            if not st.session_state.banco_dados["assinantes"]:
                st.error("ERRO: Nenhum lote de documento ativo.")
            elif not campo_nome_cliente or not campo_cpf_cliente:
                st.error("ERRO: Preencha Nome e CPF.")
            else:
                encontrado = False
                for a in st.session_state.banco_dados["assinantes"]:
                    if a["nome"].lower() == campo_nome_cliente.lower() and a["status"] == "Pendente":
                        a["status"] = "Assinado"
                        a["cpf"] = campo_cpf_cliente
                        a["data"] = "24/06/2026 14:35"
                        encontrado = True
                        break
                
                if not encontrado:
                    st.error("ERRO: Nome inválido, não cadastrado ou já assinado. Verifique a grafia exata enviada no seu e-mail

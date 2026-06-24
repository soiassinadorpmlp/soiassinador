import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="Plataforma",
    page_icon="🖋️",
    layout="wide"
)

# --- CONFIGURAÇÕES FIXAS ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://soiassinador.streamlit.app"

# --- MEMÓRIA DO SISTEMA ---
if "banco_dados" not in st.session_state:
    st.session_state.banco_dados = {
        "caminho_original": None,
        "conteudo_original": None,
        "hash_seguranca": None,
        "assinantes": []
    }

# --- LEITURA DO TOKEN DA URL ---
token_acesso = st.query_params.get("token", None)

def obter_tabela_historico():
    if not st.session_state.banco_dados["assinantes"]:
        return []
    dados = []
    for a in st.session_state.banco_dados["assinantes"]:
        dados.append({
            "Nome": a["nome"],
            "E-mail": a["email"],
            "Status": a["status"],
            "CPF": a["cpf"],
            "Data": a["data"]
        })
    return dados

# --- MOTOR DE DISPARO DE E-MAIL ---
def enviar_email_individual(meu_email, minha_senha, destino, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = destino
        msg['Subject'] = "Assinatura Digital Pendente"
        
        corpo = f"""Olá, {nome}.

Você foi incluído para assinar um documento oficial.

Acesse pelo link seguro abaixo:
{link}

Digite seu NOME e CPF para validar. Não precisa de login.
"""
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        servidor = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        servidor.login(meu_email, minha_senha)
        servidor.sendmail(meu_email, destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- PROCESSAR ENTRADA DE LOTE ---
def criador_processa_lote(arquivo, texto, meu_email, minha_senha, link_sistema):
    if arquivo is None or not texto.strip():
        return st.error("Erro: Preencha o arquivo e a lista.")
    
    st.session_state.banco_dados["caminho_original"] = arquivo.name
    st.session_state.banco_dados["conteudo_original"] = arquivo.getvalue()
    st.session_state.banco_dados["assinantes"] = []
    
    hasher = hashlib.sha256()
    hasher.update(st.session_state.banco_dados["conteudo_original"])
    st.session_state.banco_dados["hash_seguranca"] = hasher.hexdigest()

    linhas = texto.strip().split("\n")
    base_url = link_sistema.split("?")[0]
    
    for linha in linhas:
        if ";" in linha:
            partes = linha.split(";")
            nome_limpo = partes[0].strip()
            email_limpo = partes[1].strip()
            token = secrets.token_hex(4)
            
            st.session_state.banco_dados["assinantes"].append({
                "nome": nome_limpo, 
                "email": email_limpo, 
                "token": token,
                "cpf": "", 
                "status": "Pendente", 
                "data": "-"
            })
            
            link_personalizado = f"{base_url}?token={token}"
            enviar_email_individual(meu_email, minha_senha, email_limpo, nome_limpo, link_personalizado)
            
    st.success("Lote enviado com sucesso!")

# --- MENU LATERAL DE ACESSO RESTRITO ---
with st.sidebar:
    st.subheader("Controle")
    modo_admin = st.checkbox("Ativar Modo Criador")
    autenticado = False
    if modo_admin:
        senha = st.text_input("Senha", type="password")
        if senha == "ChaveMestra123":
            st.success("Liberado")
            autenticado = True

if token_acesso:
    autenticado = False

# --- ABAS ---
if autenticado:
    aba1, aba2, aba3 = st.tabs(["Criador", "Assinante", "Histórico"])
else:
    aba2, = st.tabs(["Assinante"])

# --- CONTEÚDO: CRIADOR ---
if autenticado:
    with aba1:
        c1, c2 = st.columns(2)
        with c1:
            m_email = st.text_input("Gmail Envio", value=GMAIL_PADRAO)
            m_senha = st.text_input("Senha App", type="password")
            m_link = st.text_input("Link App", value=LINK_SISTEMA_PADRAO)
            m_arq = st.file_uploader("Contrato PDF", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            if st.button("🚀 Enviar Lote", type="primary"):
                criador_processa_lote(m_arq, m_lote, m_email, m_senha, m_link)
        with c2:
            st.subheader("Painel")
            st.info("Aguardando processo...")

# --- CONTEÚDO: ASSINANTE ---
with aba2:
    st.title("🖋️ Assinatura Eletrônica")
    
    assinante_atual = None
    if token_acesso and st.session_state.banco_dados["assinantes"]:
        for a in st.session_state.banco_dados["assinantes"]:
            if str(a["token"]) == str(token_acesso):
                assinante_atual = a
                break

    st.subheader("1. Minuta para Leitura")
    if st.session_state.banco_dados["conteudo_original"] is not None:
        st.download_button(
            label="📖 Baixar minuta para leitura",
            data=st.session_state.banco_dados["conteudo_original"],
            file_name="minuta.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("Nenhum documento ativo no momento.")

    st.subheader("2. Identificação")
    nome_sug = assinante_atual["nome"] if assinante_atual else ""
    c_nome = st.text_input("Nome Completo", value=nome_sug)
    c_cpf = st.text_input("CPF")
    
    if st.button("✍️ Confirmar Assinatura", type="primary"):
        if not st.session_state.banco_dados["assinantes"]:
            st.error("Erro: Sem documento ativo.")
        elif not c_nome or not c_cpf:
            st.error("Erro: Preencha os campos.")
        else:
            encontrado = False
            for a in st.session_state.banco_dados["assinantes"]:
                valido = False
                if token_acesso:
                    valido = (str(a["token"]) == str(token_acesso) and a["status"] == "Pendente")
                else:
                    valido = (a["nome"].lower() == c_nome.lower() and a["status"] == "Pendente")
                    
                if valido:
                    a["status"] = "Assinado"
                    a["cpf"] = c_cpf
                    a["data"] = "24/06/2026"
                    encontrado = True
                    break
            
            if not encontrado:
                st.error("Erro: Inválido ou já assinado.")
            else:
                st.success("Assinatura registrada!")
                
                # COMPILAR ARQUIVO FINAL SEM CORTE DE LINHAS
                escritor = PdfWriter()
                with open("temp.pdf", "wb") as f:
                    f.write(st.session_state.banco_dados["conteudo_original"])
                for p in PdfReader("temp.pdf").pages:
                    escritor.add_page(p)
                with open("final.pdf", "wb") as f:
                    escritor.write(f)
                with open("final.pdf", "rb") as f:
                    st.session_state.pdf_final_bytes = f.read()

    st.subheader("Status")
    todos = all(x["status"] == "Assinado" for x in st.session_state.banco_dados["assinantes"]) if st.session_state.banco_dados["assinantes"] else False
    if "pdf_final_bytes" in st.session_state:
        if todos:
            st.balloons()
            st.download_button(
                label="📥 Baixar PDF Concluído",
                data=st.session_state.pdf_final_bytes,
                file_name="concluido.pdf",
                mime="application/pdf"
            )
        else:
            st.warning("Aguardando as demais assinaturas.")

# --- CONTEÚDO: HISTÓRICO ---
if autenticado:
    with aba3:
        st.subheader("Status do Lote")
        tabela = obter_tabela_historico()
        if tabela:
            st.dataframe(tabela, use_container_width=True)

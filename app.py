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
        
        corpo = f"Olá, {nome_assinante}.\n\nVocê foi incluído como assinante de um documento.\nAcesse o sistema e digite seu CPF para assinar.\n"
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        servidor = smtplib.SMTP_SSL(servidor_smtp, porta)
        servidor.login(meu_email, minha_senha_app)
        servidor.sendmail(meu_email, email_destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- PROCESSAR ENTRADA DE LOTE ---
def criador_processa_lote(arquivo_pdf, texto_assinantes, meu_email, minha_senha_app):
    if arquivo_pdf is None:
        return st.error("ERRO: Anexe um arquivo PDF.")
    if not texto_assinantes.strip():
        return st.error("ERRO: Insira pelo menos 1 assinante.")
    if not meu_email or not minha_senha_app:
        return st.error("ERRO: Configure suas credenciais de e-mail.")

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
            link_simulado = "Acesse a aba do assinante no menu superior."
            
            st.session_state.banco_dados["assinantes"].append({
                "nome": nome, "email": email, "token": token,
                "cpf": "", "status": "Pendente", "data": "-"
            })
            
            sucesso = enviar_email_individual(meu_email, minha_senha_app, email, nome, link_simulado)
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
        campo_arquivo = st.file_uploader("Arraste o PDF do Contrato", type=["pdf"])
        campo_lote = st.text_area(
            "Lista de Assinantes (Formato: Nome; E-mail)", 
            placeholder="João Silva; joao@email.com\nCarlos Roberto; carlos@email.com",
            height=150
        )
        if st.button("🚀 Disparar E-mails para o Lote", type="primary"):
            criador_processa_lote(campo_arquivo, campo_lote, campo_meu_email, campo_minha_senha)
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
        campo_nome_cliente = st.text_input("Nome Completo do Assinante")
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
                    st.error("ERRO: Nome inválido, não cadastrado ou já assinado.")
                else:
                    st.success(f"Obrigado, {campo_nome_cliente}! Assinatura registrada.")
                    
                    # GERAR FOLHA DE ASSINATURAS
                    pdf_folha = "folha_assinaturas_lote.pdf"
                    c = canvas.Canvas(pdf_folha, pagesize=letter)
                    c.setLineWidth(1)
                    c.setStrokeColorRGB(0.7, 0.7, 0.7)
                    c.rect(40, 40, 532, 712)
                    c.setFont("Helvetica-Bold", 16)
                    c.setFillColorRGB(0.1, 0.2, 0.4)
                    c.drawString(60, 710, "PROTOCOLO DE ASSINATURAS DIGITAIS")
                    c.setFont("Helvetica", 10)
                    c.setFillColorRGB(0.3, 0.3, 0.3)
                    c.drawString(60, 690, "Identificador Único (Hash SHA-256) do Original:")
                    c.setFont("Helvetica-Oblique", 9)
                    c.drawString(60, 675, f"{st.session_state.banco_dados['hash_seguranca']}")
                    c.setLineWidth(0.5)
                    c.line(60, 660, 552, 660)
                    
                    y = 620
                    for a in st.session_state.banco_dados["assinantes"]:
                        if y < 80:
                            c.showPage()
                            y = 710
                        c.setFillColorRGB(0.96, 0.96, 0.98)
                        c.rect(60, y - 45, 492, 55, fill=1, stroke=0)
                        c.setFillColorRGB(0, 0, 0)
                        c.setFont("Helvetica-Bold", 11)
                        c.drawString(70, y, f"Assinante: {a['nome']}")
                        c.setFont("Helvetica", 9)
                        c.setFillColorRGB(0.2, 0.2, 0.2)
                        c.drawString(70, y - 18, f"E-mail: {a['email']}")
                        
                        if a["status"] == "Assinado":
                            c.setFillColorRGB(0.1, 0.5, 0.2)
                            status_texto = f"STATUS: ASSINADO | CPF: {a['cpf']} | Data: {a['data']}"
                        else:
                            c.setFillColorRGB(0.7, 0.1, 0.1)
                            status_texto = "STATUS: PENDENTE"
                        c.setFont("Helvetica-Bold", 9)
                        c.drawString(70, y - 34, status_texto)
                        y -= 70
                    c.save()

                    # COMPILAR ARQUIVO FINAL
                    pdf_final_caminho = "documento_lote_finalizado.pdf"
                    escritor = PdfWriter()
                    
                    with open("temp_orig.pdf", "wb") as f_temp:
                        f_temp.write(st.session_state.banco_dados["conteudo_original"])
                        
                    for pagina in PdfReader("temp_orig.pdf").pages:
                        escritor.add_page(pagina)
                    for pagina in PdfReader(pdf_folha).pages:
                        escritor.add_page(pagina)
                        
                    escritor.encrypt(user_password="", owner_password="ChaveMestra123", permissions_flag=4)
                    with open(pdf_final_caminho, "wb") as f:
                        escritor.write(f)
                        
                    with open(pdf_final_caminho, "rb") as f_final:
                        st.session_state.pdf_final_bytes = f_final.read()
                    st.rerun()

    with col4:
        st.subheader("Acompanhamento")
        todos_assinaram = all(a["status"] == "Assinado" for a in st.session_state.banco_dados["assinantes"]) if st.session_state.banco_dados["assinantes"] else False
        
        if "pdf_final_bytes" in st.session_state:
            if todos_assinaram:
                st.balloons()
                st.success("Perfeito! Todos assinaram o documento.")
            else:
                st.warning("Assinatura salva. Aguardando os demais participantes.")
                
            st.download_button(
                label="📥 Baixar PDF Final com Protocolo",
                data=st.session_state.pdf_final_bytes,
                file_name="contrato_finalizado.pdf",
                mime="application/pdf"
            )

with aba3:
    st.subheader("Monitoramento do Lote Ativo")
    tabela = obter_tabela_historico()
    if tabela:
        st.dataframe(tabela, use_container_width=True)
    else:
        st.info("Nenhum documento sendo processado no momento.")
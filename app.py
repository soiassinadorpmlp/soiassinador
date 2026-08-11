# --- CONTEÚDO: CRIADOR ---
if st.session_state.autenticado:
    with aba1:
        c1, c2 = st.columns(2)
        with c1:
            m_email = st.text_input("Gmail Envio", value=GMAIL_PADRAO, key="input_gmail")
            m_senha = st.text_input("Senha App", type="password", key="input_senha")
            m_link = st.text_input("Link App", value=LINK_SISTEMA_PADRAO, key="input_link")
            
            m_orgao = st.text_input("Nome do Órgão / Setor responsável (Ex: Secretaria de Obras)", key="input_orgao")
            m_nome_doc = st.text_input("Nome de Identificação do Arquivo (Ex: Contrato_Locacao_01)", key="input_nome_doc")
            
            m_arq = st.file_uploader("Contrato PDF (Minuta)", type=["pdf"], key="input_pdf")
            m_lote = st.text_area("Lista (Nome; Email)", key="input_lote")
            
            if st.button("🚀 Enviar Lote", type="primary"):
                # Verificação individual para avisar exatamente qual campo falta
                erros_validacao = []
                if not m_email.strip(): erros_validacao.append("Gmail Envio")
                if not m_senha.strip(): erros_validacao.append("Senha App")
                if not m_orgao.strip(): erros_validacao.append("Órgão / Setor responsável")
                if not m_nome_doc.strip(): erros_validacao.append("Nome de Identificação do Arquivo")
                if m_arq is None: erros_validacao.append("Contrato PDF (Minuta)")
                if not m_lote.strip(): erros_validacao.append("Lista (Nome; Email)")

                if erros_validacao:
                    st.error(f"Atenção! Preencha os seguintes campos obrigatórios: {', '.join(erros_validacao)}.")
                else:
                    pdf_conteudo = m_arq.getvalue()
                    
                    st.info("Processando e salvando a minuta com segurança...")
                    
                    nome_final_pdf = m_nome_doc.strip().replace(" ", "_")
                    if not nome_final_pdf.lower().endswith(".pdf"):
                        nome_final_pdf += ".pdf"
                    
                    token_do_lote = secrets.token_hex(4)
                    nome_salvo_local = f"{token_do_lote}_{nome_final_pdf}"
                    
                    caminho_final = os.path.join(PASTA_LOCAL_MINUTAS, nome_salvo_local)
                    try:
                        with open(caminho_final, "wb") as f:
                            f.write(pdf_conteudo)
                        sucesso_salvamento = True
                    except Exception as e_save:
                        st.error(f"Erro ao salvar arquivo no servidor: {e_save}")
                        sucesso_salvamento = False
                    
                    if sucesso_salvamento:
                        hasher = hashlib.sha256()
                        hasher.update(pdf_conteudo)
                        hash_seguranca = hasher.hexdigest()
                        
                        fuso_br = timezone(timedelta(hours=-3))
                        data_criacao_lote = datetime.now(fuso_br).strftime("%d/%m/%Y")
                        
                        linhas = m_lote.strip().split("\n")
                        base_url = m_link.split("?")[0]
                        novos_assinantes = []
                        
                        progresso = st.progress(0)
                        total = len(linhas)
                        
                        for idx, inline in enumerate(linhas):
                            if ";" in inline:
                                partes = inline.split(";")
                                nome_limpo = partes[0].strip()
                                email_limpo = partes[1].strip()
                                token = secrets.token_hex(4)
                                
                                novos_assinantes.append({
                                    "token": token,
                                    "nome": nome_limpo,
                                    "email": email_limpo,
                                    "cpf": "",
                                    "status": "Pendente",
                                    "data": "-",
                                    "hash_doc": hash_seguranca,
                                    "link_minuta": nome_salvo_local,
                                    "setor": m_orgao.strip(),
                                    "data_criacao": data_criacao_lote
                                })
                                
                                link_personalizado = f"{base_url}?token={token}"
                                enviar_email_individual(
                                    meu_email=m_email, 
                                    minha_senha=m_senha, 
                                    destino=email_limpo, 
                                    nome=nome_limpo, 
                                    link=link_personalizado,
                                    orgao_setor=m_orgao.strip(),
                                    nome_documento=m_nome_doc.strip()
                                )
                            progresso.progress((idx + 1) / total)
                        
                        lista_updated = lista_banco + novos_assinantes if lista_banco else novos_assinantes
                        salvar_dados_planilha(lista_updated)
                        st.success("Lote enviado e gravado com sucesso!")
                        st.rerun()

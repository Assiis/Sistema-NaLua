from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import plotly.express as px
import streamlit as st

import db

st.set_page_config(
    page_title="NaLua — Estoque e Financeiro",
    page_icon="🍧",
    layout="wide",
)

st.markdown(
    """
    <style>
        .block-container { padding-top: 1.4rem; }
        div[data-testid="stMetric"] {
            background: #f4fbff;
            border: 1px solid #d7eef5;
            border-radius: 14px;
            padding: 12px 16px;
        }
        /* Força a cor do texto e do número para azul escuro */
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #0f4c5c !important;
        }
        h1, h2, h3 { color: #0f4c5c; }
    </style>
    """,
    unsafe_allow_html=True,
)


def brl(valor):
    numero = Decimal(str(valor or 0))
    texto = f"{numero:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def para_decimal(valor):
    if valor is None or valor == "":
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return Decimal("0")


def conectar():
    try:
        db.iniciar_schema()
        return True
    except Exception as exc:
        st.error(
            "Não foi possível conectar no PostgreSQL.\n\n"
            "1. Suba o banco com `docker compose up -d` **ou** use um PostgreSQL local.\n"
            "2. Copie `.env.example` para `.env` e confira usuário, senha e nome do banco.\n\n"
            f"Detalhe: {exc}"
        )
        return False


def recarregar():
    st.rerun()


def aba_inicio():
    estoque = db.resumo_estoque()
    hoje = db.relatorio_vendas("diario")
    semana = db.relatorio_vendas("semanal")
    mes = db.relatorio_vendas("mensal")

    st.subheader("Resumo do estoque")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Geladinhos no estoque", int(estoque["pecas"]))
    c2.metric("Valor de custo do estoque", brl(estoque["valor_custo"]))
    c3.metric("Valor de venda do estoque", brl(estoque["valor_venda"]))
    c4.metric("Lucro potencial", brl(estoque["lucro_potencial"]))

    st.subheader("Vendas")
    d1, d2, d3 = st.columns(3)
    d1.metric("Hoje — receita", brl(hoje["resumo"]["receita"]), f"{hoje['resumo']['qtd_vendas']} vendas")
    d2.metric("Semana — receita", brl(semana["resumo"]["receita"]))
    d3.metric("Mês — receita", brl(mes["resumo"]["receita"]))

    e1, e2, e3 = st.columns(3)
    e1.metric("Hoje — lucro", brl(hoje["resumo"]["lucro"]))
    e2.metric("Semana — lucro", brl(semana["resumo"]["lucro"]))
    e3.metric("Mês — lucro", brl(mes["resumo"]["lucro"]))

    produtos = db.listar_produtos()
    baixos = [p for p in produtos if p["quantidade"] <= 10]
    if baixos:
        nomes = ", ".join(f"{p['nome']} ({p['quantidade']})" for p in baixos)
        st.warning(f"Estoque baixo (10 ou menos): {nomes}")

    if hoje["ranking"]:
        st.subheader("Mais vendidos hoje")
        ranking = pd.DataFrame(hoje["ranking"])
        ranking = ranking.rename(columns={"nome_produto": "Sabor", "quantidade_vendida": "Qtd"})
        fig = px.bar(ranking, x="Sabor", y="Qtd", color="Qtd", color_continuous_scale="Teal")
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


def aba_estoque():
    st.subheader("Cadastrar sabor")
    with st.form("novo_produto", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        nome = col1.text_input("Nome do item")
        quantidade = col2.number_input("Quantidade", min_value=0, step=1, value=0)
        custo = col3.number_input("Custo unitário (R$)", min_value=0.0, step=0.10, format="%.2f")
        preco = col4.number_input("Preço de venda (R$)", min_value=0.0, step=0.10, format="%.2f")
        lucro = Decimal(str(preco)) - Decimal(str(custo))
        st.caption(f"Lucro por unidade: **{brl(lucro)}**")
        if st.form_submit_button("Salvar produto", type="primary"):
            if not nome.strip():
                st.error("Informe o nome do geladinho.")
            elif preco < custo:
                st.error("O preço de venda está menor que o custo.")
            else:
                try:
                    db.criar_produto(nome, int(quantidade), Decimal(str(custo)), Decimal(str(preco)))
                    st.success(f"{nome} cadastrado.")
                    recarregar()
                except Exception as exc:
                    st.error(f"Não foi possível cadastrar: {exc}")

    st.subheader("Estoque atual")
    st.caption("Edite o nome, a quantidade, o custo ou o preço. O lucro e os totais são calculados sozinhos.")
    produtos = db.listar_produtos()
    if not produtos:
        st.info("Nenhum item cadastrado ainda.")
        renderizar_estoque_auxiliar(
            tipo="ingredientes",
            titulo="Estoque de ingredientes",
            singular="ingrediente",
            formulario_key="novo_ingrediente",
            editor_key="editor_ingredientes",
        )
        renderizar_estoque_auxiliar(
            tipo="embalagens",
            titulo="Estoque de embalagens",
            singular="embalagem",
            formulario_key="nova_embalagem",
            editor_key="editor_embalagens",
        )
        return

    tabela = pd.DataFrame(produtos)
    editor = tabela[["id", "nome", "quantidade", "custo_unitario", "preco_venda"]].copy()
    editor["lucro_unitario"] = editor["preco_venda"] - editor["custo_unitario"]
    editor["total_item_custo"] = editor["quantidade"] * editor["custo_unitario"]
    editor["total_item_venda"] = editor["quantidade"] * editor["preco_venda"]
    editor = editor.rename(
        columns={
            "id": "ID",
            "nome": "Nome",
            "quantidade": "Quantidade",
            "custo_unitario": "Custo (R$)",
            "preco_venda": "Venda (R$)",
            "lucro_unitario": "Lucro (R$)",
            "total_item_custo": "Total custo",
            "total_item_venda": "Total venda",
        }
    )

    editado = st.data_editor(
        editor,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["ID", "Lucro (R$)", "Total custo", "Total venda"],
        column_config={
            "Quantidade": st.column_config.NumberColumn(min_value=0, step=1),
            "Custo (R$)": st.column_config.NumberColumn(format="%.2f", min_value=0.0, step=0.10),
            "Venda (R$)": st.column_config.NumberColumn(format="%.2f", min_value=0.0, step=0.10),
            "Lucro (R$)": st.column_config.NumberColumn(format="%.2f"),
            "Total custo": st.column_config.NumberColumn(format="%.2f"),
            "Total venda": st.column_config.NumberColumn(format="%.2f"),
        },
        key="editor_estoque",
    )

    if st.button("Salvar alterações do estoque", type="primary"):
        try:
            for _, linha in editado.iterrows():
                db.atualizar_produto(
                    int(linha["ID"]),
                    str(linha["Nome"]),
                    int(linha["Quantidade"]),
                    para_decimal(linha["Custo (R$)"]),
                    para_decimal(linha["Venda (R$)"]),
                )
            st.success("Estoque atualizado.")
            recarregar()
        except Exception as exc:
            st.error(f"Não foi possível salvar: {exc}")

    resumo = db.resumo_estoque()
    t1, t2, t3 = st.columns(3)
    t1.metric("Valor total de custo", brl(resumo["valor_custo"]))
    t2.metric("Valor total de venda", brl(resumo["valor_venda"]))
    t3.metric("Lucro total potencial", brl(resumo["lucro_potencial"]))

    st.subheader("Remover item da lista")
    opcoes = {f"{p['nome']} (#{p['id']})": p["id"] for p in produtos}
    escolhido = st.selectbox("Escolha o sabor", list(opcoes.keys()))
    if st.button("Esconder este item"):
        db.desativar_produto(opcoes[escolhido])
        st.success("Item removido da lista. O histórico de vendas continua salvo.")
        recarregar()

    renderizar_estoque_auxiliar(
        tipo="ingredientes",
        titulo="Estoque de ingredientes",
        singular="ingrediente",
        formulario_key="novo_ingrediente",
        editor_key="editor_ingredientes",
    )
    renderizar_estoque_auxiliar(
        tipo="embalagens",
        titulo="Estoque de embalagens",
        singular="embalagem",
        formulario_key="nova_embalagem",
        editor_key="editor_embalagens",
    )


def renderizar_estoque_auxiliar(tipo, titulo, singular, formulario_key, editor_key):
    st.subheader(titulo)
    with st.form(formulario_key, clear_on_submit=True):
        col1, col2 = st.columns(2)
        nome = col1.text_input(f"Nome da {singular}")
        quantidade = col2.number_input("Quantidade", min_value=0, step=1, value=0)
        if st.form_submit_button(f"Salvar {singular}", type="primary"):
            if not nome.strip():
                st.error(f"Informe o nome da {singular}.")
            else:
                try:
                    db.criar_estoque_auxiliar(tipo, nome, int(quantidade))
                    st.success(f"{nome} cadastrado.")
                    recarregar()
                except Exception as exc:
                    st.error(f"Não foi possível cadastrar: {exc}")

    itens = db.listar_estoque_auxiliar(tipo)
    if not itens:
        st.info(f"Nenhum {singular} cadastrado ainda.")
        return

    tabela = pd.DataFrame(itens)
    tabela["status"] = tabela["quantidade"].apply(
        lambda qtd: "Esgotado" if qtd == 0 else "Acabando" if qtd <= 10 else "Normal"
    )
    editor = tabela.rename(
        columns={"id": "ID", "nome": "Nome", "quantidade": "Quantidade", "status": "Status"}
    )
    editado = st.data_editor(
        editor[["ID", "Nome", "Quantidade", "Status"]],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["ID", "Status"],
        column_config={
            "Quantidade": st.column_config.NumberColumn(min_value=0, step=1),
            "Status": st.column_config.TextColumn(),
        },
        key=editor_key,
    )

    baixos = tabela[tabela["quantidade"] <= 10]
    if not baixos.empty:
        nomes = ", ".join(f"{linha['nome']} ({linha['quantidade']})" for _, linha in baixos.iterrows())
        st.warning(f"Atenção: {singular}s acabando ou esgotados: {nomes}.")
    else:
        st.success(f"Todos os {singular}s estão com estoque normal.")

    if st.button(f"Salvar alterações de {titulo.lower()}", type="primary", key=f"salvar_{tipo}"):
        try:
            for _, linha in editado.iterrows():
                db.atualizar_estoque_auxiliar(
                    tipo, int(linha["ID"]), str(linha["Nome"]), int(linha["Quantidade"])
                )
            st.success(f"{titulo} atualizado.")
            recarregar()
        except Exception as exc:
            st.error(f"Não foi possível salvar: {exc}")


def aba_vendas():
    st.subheader("Registrar venda")
    produtos = db.listar_produtos()
    if not produtos:
        st.info("Cadastre um sabor na aba Estoque antes de vender.")
        return

    colunas = st.columns(3)
    for i, produto in enumerate(produtos):
        with colunas[i % 3]:
            st.markdown(f"**{produto['nome']}**")
            st.caption(
                f"Estoque: {produto['quantidade']} · "
                f"Venda {brl(produto['preco_venda'])} · "
                f"Lucro {brl(produto['lucro_unitario'])}"
            )
            st.number_input(
                f"Quantidade de {produto['nome']}",
                min_value=0,
                max_value=max(int(produto["quantidade"]), 0),
                step=1,
                value=0,
                key=f"qtd_{produto['id']}",
                label_visibility="collapsed",
            )

    itens = []
    mapa = {p["id"]: p for p in produtos}
    for produto in produtos:
        qtd = int(st.session_state.get(f"qtd_{produto['id']}", 0) or 0)
        if qtd > 0:
            itens.append({"produto_id": produto["id"], "quantidade": qtd})

    total = sum(Decimal(mapa[i["produto_id"]]["preco_venda"]) * i["quantidade"] for i in itens)
    lucro = sum(Decimal(mapa[i["produto_id"]]["lucro_unitario"]) * i["quantidade"] for i in itens)

    st.markdown(f"**Total da venda:** {brl(total)} · **Lucro desta venda:** {brl(lucro)}")

    c1, c2 = st.columns(2)
    if c1.button("Confirmar venda", type="primary", disabled=not itens):
        try:
            resultado = db.registrar_venda(itens)
            for produto in produtos:
                st.session_state[f"qtd_{produto['id']}"] = 0
            st.session_state["ultima_venda"] = (
                f"Venda #{resultado['venda_id']} registrada. "
                f"Receita {brl(resultado['total_venda'])} · "
                f"Lucro {brl(resultado['total_lucro'])}."
            )
            recarregar()
        except Exception as exc:
            st.error(str(exc))
    if c2.button("Limpar seleção"):
        for produto in produtos:
            st.session_state[f"qtd_{produto['id']}"] = 0
        recarregar()

    if st.session_state.get("ultima_venda"):
        st.success(st.session_state.pop("ultima_venda"))


def aba_relatorios():
    st.subheader("Relatórios de vendas")
    col1, col2 = st.columns([1, 2])
    periodo = col1.radio("Período", ["diario", "semanal", "mensal"], format_func=lambda x: {
        "diario": "Diário",
        "semanal": "Semanal",
        "mensal": "Mensal",
    }[x], horizontal=True)
    data_ref = col2.date_input("Data de referência", value=date.today())

    dados = db.relatorio_vendas(periodo, data_ref)
    resumo = dados["resumo"]
    ranking = dados["ranking"]

    st.caption(
        f"De {dados['inicio'].strftime('%d/%m/%Y %H:%M')} "
        f"até {dados['fim'].strftime('%d/%m/%Y %H:%M')}"
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vendas", int(resumo["qtd_vendas"]))
    m2.metric("Receita", brl(resumo["receita"]))
    m3.metric("Custo", brl(resumo["custo"]))
    m4.metric("Lucro", brl(resumo["lucro"]))

    if not ranking:
        st.info("Nenhuma venda neste período.")
        return

    tabela = pd.DataFrame(ranking)
    tabela = tabela.rename(
        columns={
            "nome_produto": "Item",
            "quantidade_vendida": "Quantidade vendida",
            "receita": "Receita",
            "custo": "Custo",
            "lucro": "Lucro",
        }
    )
    st.dataframe(
        tabela,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Receita": st.column_config.NumberColumn(format="R$ %.2f"),
            "Custo": st.column_config.NumberColumn(format="R$ %.2f"),
            "Lucro": st.column_config.NumberColumn(format="R$ %.2f"),
        },
    )

    fig = px.bar(
        tabela,
        x="Item",
        y="Quantidade vendida",
        color="Quantidade vendida",
        color_continuous_scale="Teal",
        title="Itens mais vendidos no período",
    )
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=380)
    st.plotly_chart(fig, use_container_width=True)

    lider = tabela.iloc[0]
    st.success(
        f"Mais vendido: **{lider['Item']}** com **{int(lider['Quantidade vendida'])}** unidades."
    )


def main():
    st.title("🍧 NaLua")
    st.caption("Controle de estoque e financeiro para geladinhos")

    if not conectar():
        st.stop()

    inicio, estoque, vendas, relatorios = st.tabs(
        ["Início", "Estoque", "Vendas", "Relatórios"]
    )
    with inicio:
        aba_inicio()
    with estoque:
        aba_estoque()
    with vendas:
        aba_vendas()
    with relatorios:
        aba_relatorios()


if __name__ == "__main__":
    main()

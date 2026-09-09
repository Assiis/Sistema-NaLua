import os
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH, override=True)

SABORES_INICIAIS = [
    ("Chocolate", Decimal("0.80"), Decimal("2.50")),
    ("Morango", Decimal("0.70"), Decimal("2.50")),
    ("Coco", Decimal("0.75"), Decimal("2.50")),
    ("Maracujá", Decimal("0.85"), Decimal("2.50")),
    ("Leite condensado", Decimal("0.90"), Decimal("3.00")),
    ("Abacaxi", Decimal("0.70"), Decimal("2.50")),
]


def _config():
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME", "nalua"),
        "user": os.getenv("DB_USER", "nalua"),
        "password": os.getenv("DB_PASSWORD", "nalua"),
    }


def _params(**overrides):
    cfg = _config()
    cfg.update(overrides)
    return {
        "host": cfg["host"],
        "port": int(cfg["port"]),
        "dbname": cfg["dbname"],
        "user": cfg["user"],
        "password": cfg["password"],
        "connect_timeout": 5,
    }


@contextmanager
def get_conn():
    with psycopg.connect(**_params(), row_factory=dict_row, autocommit=False) as conn:
        yield conn


def _banco_nao_existe(exc):
    mensagem = str(exc).lower()
    return "does not exist" in mensagem or "não existe" in mensagem or "nao existe" in mensagem


def garantir_banco():
    cfg = _config()
    try:
        with psycopg.connect(**_params()) as conn:
            conn.close()
            return
    except psycopg.OperationalError as exc:
        if not _banco_nao_existe(exc):
            raise RuntimeError(
                "Não foi possível conectar no PostgreSQL. "
                "Confira se o serviço está ligado e os dados do arquivo .env."
            ) from exc

    admin = _params(dbname="postgres")
    with psycopg.connect(**admin, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (cfg["dbname"],))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{cfg["dbname"]}"')


def iniciar_schema():
    garantir_banco()
    sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("SELECT COUNT(*) AS total FROM produtos")
            if cur.fetchone()["total"] == 0:
                cur.executemany(
                    """
                    INSERT INTO produtos (nome, quantidade, custo_unitario, preco_venda)
                    VALUES (%s, 0, %s, %s)
                    """,
                    SABORES_INICIAIS,
                )
        conn.commit()


def listar_produtos(somente_ativos=True):
    sql = """
        SELECT
            id,
            nome,
            quantidade,
            custo_unitario,
            preco_venda,
            (preco_venda - custo_unitario) AS lucro_unitario,
            (quantidade * custo_unitario) AS total_custo,
            (quantidade * preco_venda) AS total_venda,
            (quantidade * (preco_venda - custo_unitario)) AS total_lucro,
            ativo
        FROM produtos
    """
    if somente_ativos:
        sql += " WHERE ativo = TRUE"
    sql += " ORDER BY nome"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()


def resumo_estoque():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(quantidade), 0) AS pecas,
                    COALESCE(SUM(quantidade * custo_unitario), 0) AS valor_custo,
                    COALESCE(SUM(quantidade * preco_venda), 0) AS valor_venda,
                    COALESCE(SUM(quantidade * (preco_venda - custo_unitario)), 0) AS lucro_potencial
                FROM produtos
                WHERE ativo = TRUE
                """
            )
            return cur.fetchone()


def criar_produto(nome, quantidade, custo_unitario, preco_venda):
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO produtos (nome, quantidade, custo_unitario, preco_venda)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (nome.strip(), quantidade, custo_unitario, preco_venda),
                )
            except UniqueViolation as exc:
                conn.rollback()
                raise ValueError("Já existe um item com esse nome.") from exc
        conn.commit()


def atualizar_produto(produto_id, nome, quantidade, custo_unitario, preco_venda, ativo=True):
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    UPDATE produtos
                    SET nome = %s,
                        quantidade = %s,
                        custo_unitario = %s,
                        preco_venda = %s,
                        ativo = %s,
                        atualizado_em = NOW()
                    WHERE id = %s
                    """,
                    (nome.strip(), quantidade, custo_unitario, preco_venda, ativo, produto_id),
                )
            except UniqueViolation as exc:
                conn.rollback()
                raise ValueError("Já existe um item com esse nome.") from exc
        conn.commit()


def desativar_produto(produto_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE produtos SET ativo = FALSE, atualizado_em = NOW() WHERE id = %s",
                (produto_id,),
            )
        conn.commit()


def registrar_venda(itens):
    if not itens:
        raise ValueError("Adicione pelo menos um item na venda.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            total_venda = Decimal("0")
            total_custo = Decimal("0")
            linhas = []

            for item in itens:
                cur.execute(
                    """
                    SELECT id, nome, quantidade, custo_unitario, preco_venda
                    FROM produtos
                    WHERE id = %s AND ativo = TRUE
                    FOR UPDATE
                    """,
                    (item["produto_id"],),
                )
                produto = cur.fetchone()
                if not produto:
                    raise ValueError("Produto não encontrado.")

                qtd = int(item["quantidade"])
                if qtd <= 0:
                    raise ValueError("A quantidade vendida precisa ser maior que zero.")
                if produto["quantidade"] < qtd:
                    raise ValueError(
                        f"Estoque insuficiente de {produto['nome']}. "
                        f"Disponível: {produto['quantidade']}."
                    )

                custo = Decimal(produto["custo_unitario"])
                preco = Decimal(produto["preco_venda"])
                lucro = preco - custo
                total_venda += preco * qtd
                total_custo += custo * qtd
                linhas.append((produto, qtd, custo, preco, lucro))

            total_lucro = total_venda - total_custo
            cur.execute(
                """
                INSERT INTO vendas (total_venda, total_custo, total_lucro)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (total_venda, total_custo, total_lucro),
            )
            venda_id = cur.fetchone()["id"]

            for produto, qtd, custo, preco, lucro in linhas:
                cur.execute(
                    """
                    INSERT INTO itens_venda (
                        venda_id, produto_id, nome_produto, quantidade,
                        custo_unitario, preco_unitario, lucro_unitario
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (venda_id, produto["id"], produto["nome"], qtd, custo, preco, lucro),
                )
                cur.execute(
                    """
                    UPDATE produtos
                    SET quantidade = quantidade - %s, atualizado_em = NOW()
                    WHERE id = %s
                    """,
                    (qtd, produto["id"]),
                )
        conn.commit()
        return {
            "venda_id": venda_id,
            "total_venda": total_venda,
            "total_custo": total_custo,
            "total_lucro": total_lucro,
        }


def _intervalo(periodo, data_ref=None):
    data_ref = data_ref or date.today()
    inicio = datetime.combine(data_ref, time.min)
    fim = datetime.combine(data_ref, time.max)

    if periodo == "diario":
        pass
    elif periodo == "semanal":
        inicio = datetime.combine(data_ref - timedelta(days=data_ref.weekday()), time.min)
        fim = inicio + timedelta(days=7) - timedelta(microseconds=1)
    elif periodo == "mensal":
        inicio = datetime.combine(data_ref.replace(day=1), time.min)
        if data_ref.month == 12:
            proximo = date(data_ref.year + 1, 1, 1)
        else:
            proximo = date(data_ref.year, data_ref.month + 1, 1)
        fim = datetime.combine(proximo, time.min) - timedelta(microseconds=1)
    else:
        raise ValueError("Período inválido.")
    return inicio, fim


def relatorio_vendas(periodo, data_ref=None):
    inicio, fim = _intervalo(periodo, data_ref)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS qtd_vendas,
                    COALESCE(SUM(total_venda), 0) AS receita,
                    COALESCE(SUM(total_custo), 0) AS custo,
                    COALESCE(SUM(total_lucro), 0) AS lucro
                FROM vendas
                WHERE data_hora BETWEEN %s AND %s
                """,
                (inicio, fim),
            )
            resumo = cur.fetchone()
            cur.execute(
                """
                SELECT
                    nome_produto,
                    SUM(quantidade) AS quantidade_vendida,
                    SUM(quantidade * preco_unitario) AS receita,
                    SUM(quantidade * custo_unitario) AS custo,
                    SUM(quantidade * lucro_unitario) AS lucro
                FROM itens_venda i
                JOIN vendas v ON v.id = i.venda_id
                WHERE v.data_hora BETWEEN %s AND %s
                GROUP BY nome_produto
                ORDER BY quantidade_vendida DESC, receita DESC
                """,
                (inicio, fim),
            )
            ranking = cur.fetchall()
    return {"inicio": inicio, "fim": fim, "resumo": resumo, "ranking": ranking}

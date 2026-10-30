import numpy as np
import pandas as pd
import pytest

from src.ui.prep.macro_prep import (
    ciclos_selic,
    correlacao,
    correlacao_defasada,
    janelas_acima_media,
    juro_real_maximos,
    kpis_macro,
    painel_mensal,
    serie_diaria,
)


@pytest.fixture
def dim_indicador_sintetica() -> pd.DataFrame:
    return pd.DataFrame([
        {"sk_indicador": 1, "codigo": "SELIC_META", "agg_mensal": "ultimo"},
        {"sk_indicador": 2, "codigo": "PTAX_VENDA", "agg_mensal": "media"},
        {"sk_indicador": 3, "codigo": "IPCA_12M", "agg_mensal": "ultimo"},
        {"sk_indicador": 4, "codigo": "JURO_REAL_EXPOST", "agg_mensal": "ultimo"},
    ])


@pytest.fixture
def fato_macro_sintetica() -> pd.DataFrame:
    datas_jan = pd.date_range("2023-01-01", "2023-01-05", freq="D")
    datas_fev = pd.date_range("2023-02-01", "2023-02-05", freq="D")
    
    rows = []
    # SELIC_META jan (ultimo = 13.75)
    for d in datas_jan:
        rows.append({"sk_tempo": int(d.strftime("%Y%m%d")), "sk_indicador": 1, "valor": 13.75, "data": d.strftime("%Y-%m-%d")})
    # PTAX_VENDA jan (media = 5.0)
    for i, d in enumerate(datas_jan):
        rows.append({"sk_tempo": int(d.strftime("%Y%m%d")), "sk_indicador": 2, "valor": 4.0 + i, "data": d.strftime("%Y-%m-%d")})
    
    # SELIC_META fev (ultimo = 12.75)
    for d in datas_fev:
        rows.append({"sk_tempo": int(d.strftime("%Y%m%d")), "sk_indicador": 1, "valor": 12.75, "data": d.strftime("%Y-%m-%d")})
    # PTAX_VENDA fev (media = 5.2)
    for i, d in enumerate(datas_fev):
        rows.append({"sk_tempo": int(d.strftime("%Y%m%d")), "sk_indicador": 2, "valor": 5.2, "data": d.strftime("%Y-%m-%d")})

    return pd.DataFrame(rows)


def test_serie_diaria(fato_macro_sintetica, dim_indicador_sintetica):
    s = serie_diaria(fato_macro_sintetica, dim_indicador_sintetica, "SELIC_META")
    assert isinstance(s, pd.Series)
    assert len(s) == 10
    assert s.iloc[0] == 13.75


def test_painel_mensal_agg_rules(fato_macro_sintetica, dim_indicador_sintetica):
    df_p = painel_mensal(fato_macro_sintetica, dim_indicador_sintetica)
    assert "2023-01" in df_p.index
    assert "2023-02" in df_p.index
    # SELIC_META: ultimo
    assert df_p.loc["2023-01", "SELIC_META"] == 13.75
    # PTAX_VENDA: media (4+5+6+7+8)/5 = 6.0
    assert df_p.loc["2023-01", "PTAX_VENDA"] == 6.0


def test_kpis_macro_janela_curta():
    painel = pd.DataFrame({
        "IPCA_12M": [5.0, 5.2],
        "JURO_REAL_EXPOST": [8.0, 8.1]
    }, index=["2023-01", "2023-02"])
    selic_d = pd.Series([13.75], index=pd.to_datetime(["2023-01-01"]))
    ptax_d = pd.Series([5.0], index=pd.to_datetime(["2023-01-01"]))

    res = kpis_macro(painel, selic_d, ptax_d)
    assert res["selic_vigente"] == 13.75
    assert res["selic_delta_12m"] is None
    assert "Janela menor que 12 meses" in res["selic_motivo"]


def test_kpis_macro_janela_completa():
    dates = pd.date_range("2022-01-01", "2023-01-01", freq="MS").strftime("%Y-%m")
    ipca_vals = np.linspace(10.0, 5.0, len(dates))
    painel = pd.DataFrame({"IPCA_12M": ipca_vals, "JURO_REAL_EXPOST": ipca_vals}, index=dates)

    d_dates = pd.date_range("2022-01-01", "2023-01-01", freq="D")
    selic_d = pd.Series(13.75, index=d_dates)
    selic_d.iloc[0] = 9.25
    ptax_d = pd.Series(5.0, index=d_dates)
    ptax_d.iloc[0] = 5.5

    res = kpis_macro(painel, selic_d, ptax_d)
    assert res["ipca_delta_12m"] == pytest.approx(5.0 - 10.0)
    assert res["selic_delta_12m"] == pytest.approx(13.75 - 9.25)


def test_ciclos_selic():
    dates = pd.date_range("2023-01-01", "2023-06-01", freq="D")
    vals = [2.0] * 50 + [3.0] * 50 + [2.5] * 52
    selic_d = pd.Series(vals, index=dates)

    ciclos = ciclos_selic(selic_d, dias_estavel=30)
    assert not ciclos.empty
    tipos = ciclos["tipo"].tolist()
    assert "aperto" in tipos or "corte" in tipos


def test_janelas_acima_media():
    dates = pd.date_range("2023-01-01", "2023-01-20", freq="D")
    vals = [4.0] * 10 + [6.0] * 10
    ptax_d = pd.Series(vals, index=dates)

    janelas = janelas_acima_media(ptax_d, minimo_dias=5)
    assert len(janelas) == 1
    assert janelas.iloc[0]["dias"] == 10


def test_correlacao_modo_niveis_e_variacoes():
    df = pd.DataFrame({
        "A": [10.0, 12.0, 15.0, 18.0, 20.0],
        "B": [100.0, 120.0, 150.0, 180.0, 200.0]
    })
    res_niveis = correlacao(df, modo="niveis")
    assert res_niveis["matriz"].loc["A", "B"] == pytest.approx(1.0)
    assert res_niveis["n_obs"] == 5

    np_corr = np.corrcoef(df["A"], df["B"])[0, 1]
    assert res_niveis["matriz"].loc["A", "B"] == pytest.approx(np_corr)


def test_correlacao_defasada():
    x = [1, 2, 3, 4, 5, 6, 7, 8]
    y = [0, 1, 2, 3, 4, 5, 6, 7]  # y e x desfasados em 1 periodo
    df = pd.DataFrame({"X": x, "Y": y})

    res = correlacao_defasada(df, "X", "Y", max_defasagem=2)
    assert len(res) == 3
    # Defasagem k=1 deve ter correlação perfeita (1.0)
    row_k1 = res[res["defasagem"] == 1]
    assert row_k1["r"].values[0] == pytest.approx(1.0)


def test_juro_real_maximos():
    painel = pd.DataFrame({
        "JURO_REAL_EXPOST": [0.05, 0.08, 0.02, 0.09, 0.01]
    }, index=["2023-01", "2023-02", "2023-03", "2023-04", "2023-05"])

    top2 = juro_real_maximos(painel, n=2)
    assert len(top2) == 2
    assert top2.iloc[0]["JURO_REAL_EXPOST"] == 0.09
    assert top2.iloc[1]["JURO_REAL_EXPOST"] == 0.08
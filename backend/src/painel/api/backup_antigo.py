"""Converte o backup do painel antigo (arquivo com "debts") para o formato versão 2.

Regras herdadas do painel antigo, aplicadas a partir do mês atual:
- conta "mudada de mês" (excluída num mês e incluída depois) começa no mês para onde foi;
- o valor da conta é o mais recente guardado por mês, menos desconto e abatimento;
- parcelada: só as parcelas que ainda faltam; quitada não vem;
- única já paga antes do início não vem;
- pagamentos a partir do mês atual são mantidos (sem banco).
"""

import math
from datetime import date
from typing import Any

from painel.domain.regras.categorias import sugerir_categoria


def _num(v: Any) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 0.0
    return n if math.isfinite(n) else 0.0


def converter_painel_antigo(o: dict[str, Any], hoje: date) -> dict[str, Any]:
    atual = f"{hoje.year:04d}-{hoje.month:02d}"
    meses: dict[str, Any] = o.get("months") or {}

    def ids(mes: str, campo: str) -> list[str]:
        return [str(x) for x in ((meses.get(mes) or {}).get(campo) or [])]

    def pago_em(conta_id: str) -> list[str]:
        return sorted(m for m in meses if conta_id in ids(m, "paidIds"))

    def valor_em(mes: str, conta_id: str) -> float | None:
        valores = (meses.get(mes) or {}).get("amounts") or {}
        if conta_id not in valores:
            return None
        try:
            n = float(valores[conta_id])
        except (TypeError, ValueError):
            return None
        return n if math.isfinite(n) else None

    contas: list[dict[str, Any]] = []
    pagamentos: dict[str, dict[str, Any]] = {}

    for d in o.get("debts") or []:
        cid = str(d.get("id"))
        corte = _num(d.get("discount")) + _num(d.get("abated"))
        pago = pago_em(cid)
        criado = d.get("createdMonth")
        inicio = criado if isinstance(criado, str) and criado > atual else atual
        if cid in ids(inicio, "excludedIds"):
            para = sorted(m for m in meses if m > inicio and cid in ids(m, "includedIds"))
            if para:
                inicio = para[0]
        com_valor = sorted(m for m in meses if m >= atual and valor_em(m, cid) is not None)
        if com_valor:
            base = valor_em(inicio if inicio in com_valor else com_valor[-1], cid) or 0.0
        else:
            base = _num(d.get("value"))
        tipo = {"fixed": "fixed", "installment": "installment"}.get(d.get("type"), "single")
        conta: dict[str, Any] = {
            "id": cid,
            "name": d.get("name") or "Conta",
            "creditor": d.get("category") or "Outros",
            "value": max(0.0, base - corte),
            "dueDay": int(_num(d.get("dueDay"))),
            "type": tipo,
            "startMonth": inicio,
            "endMonth": None,
            "startNumber": 1,
            "total": 1,
            "highInterest": bool(d.get("highInterest")),
            "uncertain": bool(d.get("uncertain")),
        }
        if tipo == "installment":
            antes = sum(1 for m in pago if m < inicio)
            restam = max(0, int(_num(d.get("startingRemaining"))) - antes)
            if restam <= 0:
                continue
            conta["total"] = max(1, int(_num(d.get("totalInstallments"))) or restam)
            conta["startNumber"] = max(1, conta["total"] - restam + 1)
        if tipo == "single":
            if any(m < inicio for m in pago):
                continue
            movida = sorted(m for m in meses if m >= atual and cid in ids(m, "includedIds"))
            if movida:
                conta["startMonth"] = movida[0]
        conta["group"] = sugerir_categoria(conta["name"], conta["creditor"])
        contas.append(conta)

        for m in (m for m in pago if m >= atual):
            chave = conta["startMonth"] if tipo == "single" else m
            if cid in pagamentos.get(chave, {}):
                continue
            v = valor_em(m, cid)
            pagamentos.setdefault(chave, {})[cid] = {
                "amount": max(0.0, (base if v is None else v) - corte),
                "accountId": None,
                "date": hoje.isoformat() if m == atual else f"{m}-01",
            }

    ganhos = [
        {
            "id": str(x.get("id")),
            "name": x.get("name") or "Ganho",
            "value": _num(x.get("value")),
            "date": x.get("date") or hoje.isoformat(),
            "received": not x.get("pending"),
            "accountId": None,
        }
        for x in o.get("incomes") or []
    ]

    bancos = []
    for i, a in enumerate(o.get("cashAccounts") or []):
        saldos = a.get("balances") or {}
        ultimo = sorted(saldos)[-1] if saldos else None
        bancos.append(
            {
                "id": str(a.get("id") or f"banco-{i}"),
                "name": a.get("name") or "Banco",
                "balance": _num(saldos[ultimo]) if ultimo else _num(a.get("balance")),
            }
        )

    sim = (meses.get(atual) or {}).get("sim") or o.get("globalSim") or {}
    return {
        "version": 2,
        "since": atual,
        "accounts": bancos,
        "incomes": ganhos,
        "bills": contas,
        "payments": pagamentos,
        "sim": {
            "weekday": _num(sim.get("weekday")),
            "weekend": _num(sim.get("weekend")),
            "on": False,
        },
    }

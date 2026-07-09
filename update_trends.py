#!/usr/bin/env python3
"""
Ticino Tourism Radar — Google Trends Updater
Esegue ogni lunedì via GitHub Actions.
Aggiorna il nodo marketing_trends in radar_data.json.

REGOLA D'ORO: se Google Trends non risponde (blocco 429, rete, ecc.),
lo script NON tocca il file. I trend esistenti restano invariati.
Meglio dati validi della settimana scorsa che "N/D" ovunque.
"""

import json
import time
import datetime
import sys

# ── Configurazione keyword e geo
KEYWORDS = ["Tessin", "Lago Maggiore", "Ascona", "Locarno", "Brissago"]
GEO_LIST = ["DE", "CH"]
TIMEFRAME = "now 7-d"

# Numero minimo di keyword con dati REALI perché valga la pena aggiornare.
# Se ne otteniamo meno di così, consideriamo il fetch fallito e non tocchiamo nulla.
MIN_KEYWORD_VALIDE = 3

NOTE = {
    "Tessin": "Termine ombrello — cattura tutto il mercato DACH verso il cantone",
    "Lago Maggiore": "Alta intent turistica, pubblico pronto a prenotare",
    "Ascona": "Brand forte, ricercato da pubblico alto-spendente svizzero-tedesco",
    "Locarno": "Picco legato al Film Festival — prenotazioni anticipate",
    "Brissago": "Nicchia premium, bassa competizione, alta conversione",
}


def fetch_trends(keywords, geo):
    """Scarica i trend per una lista di keyword e un geo. Ritorna un DataFrame o None."""
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl="de-DE", tz=60, timeout=(10, 25))
    pytrends.build_payload(keywords, cat=0, timeframe=TIMEFRAME, geo=geo)
    time.sleep(2)  # evita rate limiting
    df = pytrends.interest_over_time()
    return df


def calcola_crescita(df, keyword):
    """
    Calcola la variazione % tra prima e seconda metà della settimana.
    Ritorna SEMPRE una tupla (delta_num, label, trend) oppure None se non calcolabile.
    """
    if df is None or df.empty or keyword not in df.columns:
        return None
    serie = df[keyword].tolist()
    if len(serie) < 4:
        return None
    meta = len(serie) // 2
    media_prima = sum(serie[:meta]) / meta if meta > 0 else 0
    media_seconda = sum(serie[meta:]) / (len(serie) - meta) if (len(serie) - meta) > 0 else 0
    if media_prima == 0:
        return (0, "Stabile", "stable")
    delta = ((media_seconda - media_prima) / media_prima) * 100
    if abs(delta) < 5:
        label, trend = "Stabile", "stable"
    elif delta > 0:
        label, trend = f"+{round(delta)}%", "up"
    else:
        label, trend = f"{round(delta)}%", "down"
    return (round(delta), label, trend)


def genera_suggerimento(keyword, trend):
    """Suggerimenti operativi concreti, dipendenti dalla direzione del trend."""
    if trend == "up":
        opzioni = {
            "Tessin": "Ricerche in crescita: usa questa keyword nei titoli di post e newsletter ora",
            "Lago Maggiore": "Onda di interesse alta: pubblica un reel del lungolago al tramonto con caption in tedesco e #LagoMaggiore #Ascona",
            "Ascona": "Domanda in salita: controlla disponibilit\u00e0 Booking e valuta un rialzo tariffario nel weekend",
            "Locarno": "Interesse in aumento: menziona le date del Film Festival nei post per intercettare chi pianifica agosto",
            "Brissago": "Trend positivo: lancia una campagna micro-targeting FB/IG verso utenti ZH/DE",
        }
        return opzioni.get(keyword, "Ricerche in crescita: aumenta la presenza social su questa keyword")
    elif trend == "down":
        opzioni = {
            "Tessin": "Ricerche in calo: la domanda si sposta su termini pi\u00f9 specifici, punta su 'Lago Maggiore' o sulla tua localit\u00e0",
            "Lago Maggiore": "Interesse in flessione: differenzia con esperienze uniche (gastronomia, eventi) invece della sola destinazione",
            "Ascona": "Ricerche in calo: rafforza il brand con contenuti di valore, non sconti che erodono il posizionamento premium",
            "Locarno": "Interesse in flessione: prepara i contenuti per il picco Film Festival, non spingere ora",
            "Brissago": "Ricerche in calo: punta sulla nicchia, evita campagne ampie poco efficienti in questa fase",
        }
        return opzioni.get(keyword, "Ricerche in calo: rivedi la strategia, non investire su questa keyword ora")
    else:  # stable
        opzioni = {
            "Tessin": "Domanda stabile: mantieni presenza costante, usa come keyword di base nei contenuti",
            "Lago Maggiore": "Interesse costante: keyword affidabile per contenuti sempreverdi e SEO di base",
            "Ascona": "Brand stabile: ottimo momento per consolidare le recensioni e la reputazione online",
            "Locarno": "Domanda costante: mantieni i contenuti aggiornati in vista dei picchi stagionali",
            "Brissago": "Nicchia stabile: punta sulla qualit\u00e0 e sulla conversione, non sul volume",
        }
        return opzioni.get(keyword, "Domanda stabile: mantieni una presenza costante su questa keyword")


def main():
    print(f"[{datetime.datetime.now()}] Avvio aggiornamento Google Trends...")

    ricerche_valide = []
    seen = set()

    for geo in GEO_LIST:
        print(f"  Fetching trends per geo={geo}...")
        try:
            df = fetch_trends(KEYWORDS, geo)
        except Exception as e:
            print(f"  Errore geo={geo}: {e}")
            continue

        for kw in KEYWORDS:
            if kw in seen:
                continue
            result = calcola_crescita(df, kw)
            if result is not None:
                delta_num, label, trend = result
                ricerche_valide.append({
                    "keyword": kw,
                    "crescita": label,
                    "trend": trend,
                    "geo": geo,
                    "note": NOTE.get(kw, ""),
                    "suggerimento_azione": genera_suggerimento(kw, trend),
                })
                seen.add(kw)
        time.sleep(3)

    # ── REGOLA D'ORO: se non abbiamo abbastanza dati REALI, non tocchiamo il file.
    if len(ricerche_valide) < MIN_KEYWORD_VALIDE:
        print(f"  ATTENZIONE: solo {len(ricerche_valide)} keyword valide "
              f"(minimo {MIN_KEYWORD_VALIDE}). Google Trends probabilmente ha bloccato la richiesta.")
        print("  Il file NON viene modificato: i trend esistenti restano invariati.")
        print(f"[{datetime.datetime.now()}] Terminato senza modifiche.")
        return  # esce SENZA scrivere → i dati buoni restano

    # Ordina: prima i trend in crescita, poi stabili, poi in calo
    ricerche_valide.sort(key=lambda x: (
        0 if x["trend"] == "up" else (1 if x["trend"] == "stable" else 2)
    ))

    # Leggi radar_data.json
    try:
        with open("radar_data.json", "r", encoding="utf-8") as f:
            radar = json.load(f)
    except Exception as e:
        print(f"  Impossibile leggere radar_data.json: {e}")
        sys.exit(1)

    # Assicura che il nodo esista
    if "marketing_trends" not in radar:
        radar["marketing_trends"] = {"mercato": "DACH (CH-DE-AT)", "social_hashtags": []}

    # Aggiorna SOLO i campi dei trend, preservando hashtag ed eventuali altri campi
    radar["marketing_trends"]["settimana"] = datetime.date.today().isoformat()
    radar["marketing_trends"]["ricerche_top"] = ricerche_valide

    with open("radar_data.json", "w", encoding="utf-8") as f:
        json.dump(radar, f, ensure_ascii=False, indent=2)

    print(f"  radar_data.json aggiornato con {len(ricerche_valide)} keyword reali")
    print(f"  Trend: {[k['keyword'] + ' ' + k['crescita'] for k in ricerche_valide]}")
    print(f"[{datetime.datetime.now()}] Completato.")


if __name__ == "__main__":
    main()

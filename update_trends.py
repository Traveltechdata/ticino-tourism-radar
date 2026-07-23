#!/usr/bin/env python3
"""
Ticino Tourism Radar — Google Trends via Apify
Sostituisce pytrends (bloccato da Google sugli IP di GitHub Actions).

USO LOCALE (dal tuo Mac, quando vuoi aggiornare):
    export APIFY_TOKEN="il_tuo_token"
    python3 update_trends_apify.py

USO IN GITHUB ACTIONS:
    aggiungi APIFY_TOKEN nei Secrets del repo e richiama lo script nel workflow.

REGOLA D'ORO (invariata): se l'aggiornamento fallisce, il file NON viene toccato.
Meglio i trend della settimana scorsa che "N/D" ovunque.
"""

import json
import os
import sys
import time
import datetime
import urllib.request
import urllib.error

# ── Configurazione
KEYWORDS = ["Tessin", "Lago Maggiore", "Ascona", "Locarno", "Brissago"]
GEO = "CH"                    # mercato di riferimento
TIMEFRAME = "now 7-d"         # ultimi 7 giorni
MIN_KEYWORD_VALIDE = 3        # sotto questa soglia consideriamo il fetch fallito

# Actor Apify per Google Trends.
# NOTA: verifica l'ID sull'Apify Store e adattalo se usi un actor diverso.
# Il formato dell'input varia da actor ad actor: vedi ADATTA_INPUT più sotto.
APIFY_ACTOR = os.environ.get("APIFY_TRENDS_ACTOR", "emastra~google-trends-scraper")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

NOTE = {
    "Tessin": "Termine ombrello — cattura tutto il mercato DACH verso il cantone",
    "Lago Maggiore": "Alta intent turistica, pubblico pronto a prenotare",
    "Ascona": "Brand forte, ricercato da pubblico alto-spendente svizzero-tedesco",
    "Locarno": "Picco legato al Film Festival — prenotazioni anticipate",
    "Brissago": "Nicchia premium, bassa competizione, alta conversione",
}


def genera_suggerimento(keyword, trend):
    """Suggerimenti operativi concreti, dipendenti dalla direzione del trend."""
    if trend == "up":
        opzioni = {
            "Tessin": "Ricerche in crescita: usa questa keyword nei titoli di post e newsletter ora",
            "Lago Maggiore": "Onda di interesse alta: pubblica un reel del lungolago al tramonto con caption in tedesco e #LagoMaggiore #Ascona",
            "Ascona": "Domanda in salita: controlla la disponibilità e valuta un rialzo tariffario nel weekend",
            "Locarno": "Interesse in aumento: menziona le date del Film Festival nei post per intercettare chi pianifica agosto",
            "Brissago": "Trend positivo: lancia una campagna micro-targeting FB/IG verso utenti ZH/DE",
        }
        return opzioni.get(keyword, "Ricerche in crescita: aumenta la presenza social su questa keyword")
    elif trend == "down":
        opzioni = {
            "Tessin": "Ricerche in calo: la domanda si sposta su termini più specifici, punta su 'Lago Maggiore' o sulla tua località",
            "Lago Maggiore": "Interesse in flessione: differenzia con esperienze uniche (gastronomia, eventi) invece della sola destinazione",
            "Ascona": "Ricerche in calo: rafforza il brand con contenuti di valore, non sconti che erodono il posizionamento premium",
            "Locarno": "Interesse in flessione: prepara i contenuti per il picco Film Festival, non spingere ora",
            "Brissago": "Ricerche in calo: punta sulla nicchia, evita campagne ampie poco efficienti in questa fase",
        }
        return opzioni.get(keyword, "Ricerche in calo: rivedi la strategia, non investire su questa keyword ora")
    else:
        opzioni = {
            "Tessin": "Domanda stabile: mantieni presenza costante, usa come keyword di base nei contenuti",
            "Lago Maggiore": "Interesse costante: keyword affidabile per contenuti sempreverdi e SEO di base",
            "Ascona": "Brand stabile: ottimo momento per consolidare le recensioni e la reputazione online",
            "Locarno": "Domanda costante: mantieni i contenuti aggiornati in vista dei picchi stagionali",
            "Brissago": "Nicchia stabile: punta sulla qualità e sulla conversione, non sul volume",
        }
        return opzioni.get(keyword, "Domanda stabile: mantieni una presenza costante su questa keyword")


def chiama_apify(keywords):
    """
    Lancia l'actor Apify e aspetta i risultati.
    Ritorna la lista di item del dataset, o None se fallisce.
    """
    if not APIFY_TOKEN:
        print("  APIFY_TOKEN non impostato. Imposta la variabile d'ambiente.")
        return None

    # ADATTA_INPUT: struttura tipica per actor Google Trends.
    # Se usi un actor diverso, controlla la sua documentazione e adatta queste chiavi.
    payload = {
        "searchTerms": keywords,
        "geo": GEO,
        "timeRange": TIMEFRAME,
        "isPublic": False,
    }

    url = ("https://api.apify.com/v2/acts/" + APIFY_ACTOR +
           "/run-sync-get-dataset-items?token=" + APIFY_TOKEN)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("  Errore HTTP Apify:", e.code, e.read()[:200])
        return None
    except Exception as e:
        print("  Errore chiamata Apify:", e)
        return None


def estrai_trend(items, keyword):
    """
    Dai risultati dell'actor ricava (label, trend) per una keyword.
    Confronta la media della prima metà del periodo con la seconda.
    ADATTA_PARSING: la forma degli item varia per actor — questa funzione
    prova le strutture più comuni.
    """
    if not items:
        return None

    serie = []
    for item in items:
        # Struttura A: {"searchTerm": "...", "interestOverTime": [{"value": n}, ...]}
        if item.get("searchTerm") == keyword or item.get("keyword") == keyword:
            iot = item.get("interestOverTime") or item.get("timelineData") or []
            for punto in iot:
                v = punto.get("value")
                if isinstance(v, list):
                    v = v[0] if v else None
                if isinstance(v, (int, float)):
                    serie.append(v)
        # Struttura B: righe piatte {"keyword": "...", "value": n, "date": "..."}
        elif item.get("keyword") == keyword and isinstance(item.get("value"), (int, float)):
            serie.append(item["value"])

    if len(serie) < 4:
        return None

    meta = len(serie) // 2
    prima = sum(serie[:meta]) / meta
    seconda = sum(serie[meta:]) / (len(serie) - meta)
    if prima == 0:
        return ("Stabile", "stable")

    delta = (seconda - prima) / prima * 100
    if abs(delta) < 5:
        return ("Stabile", "stable")
    elif delta > 0:
        return ("+" + str(round(delta)) + "%", "up")
    else:
        return (str(round(delta)) + "%", "down")


def main():
    print("[%s] Aggiornamento Google Trends via Apify..." % datetime.datetime.now())

    items = chiama_apify(KEYWORDS)
    if items is None:
        print("  Chiamata fallita. Il file NON viene modificato.")
        return

    ricerche = []
    for kw in KEYWORDS:
        res = estrai_trend(items, kw)
        if res:
            label, trend = res
            ricerche.append({
                "keyword": kw,
                "crescita": label,
                "trend": trend,
                "geo": GEO,
                "note": NOTE.get(kw, ""),
                "suggerimento_azione": genera_suggerimento(kw, trend),
            })

    if len(ricerche) < MIN_KEYWORD_VALIDE:
        print("  Solo %d keyword valide (minimo %d). Il file NON viene modificato."
              % (len(ricerche), MIN_KEYWORD_VALIDE))
        return

    ricerche.sort(key=lambda x: 0 if x["trend"] == "up" else (1 if x["trend"] == "stable" else 2))

    try:
        with open("radar_data.json", "r", encoding="utf-8") as f:
            radar = json.load(f)
    except Exception as e:
        print("  Impossibile leggere radar_data.json:", e)
        sys.exit(1)

    if "marketing_trends" not in radar:
        radar["marketing_trends"] = {"mercato": "DACH (CH-DE-AT)", "social_hashtags": []}

    radar["marketing_trends"]["settimana"] = datetime.date.today().isoformat()
    radar["marketing_trends"]["ricerche_top"] = ricerche

    with open("radar_data.json", "w", encoding="utf-8") as f:
        json.dump(radar, f, ensure_ascii=False, indent=2)

    print("  Aggiornate %d keyword: %s" % (len(ricerche),
          [r["keyword"] + " " + r["crescita"] for r in ricerche]))
    print("[%s] Completato." % datetime.datetime.now())


if __name__ == "__main__":
    main()

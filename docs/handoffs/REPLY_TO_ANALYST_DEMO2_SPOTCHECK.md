Spot-check Demo #2 (Generale 4h) M3 "Diritti e doveri" — 56 titoli CONTENT_TEXT/IMAGE classificati.

═══════════════════════════════════════════════════════════════════
RIEPILOGO NUMERICO (su 56 titoli content)
═══════════════════════════════════════════════════════════════════

  ON-TOPIC vero (diritti/doveri lavoratori art. 19-20):  18 (32%)
  FORMAZIONE adiacente legittima:                         10 (18%)
  ALTRO ADIACENTE LEGITTIMO:                              15 (27%)
    - medico competente / sorveglianza (6)
    - sanzioni-come-dovere (responsabilità penali) (9)
  OFF-TOPIC chiari:                                       13 (23%)

I 13 off-topic sono distribuiti in 3 sottogruppi visivamente
riconoscibili:

  GRUPPO A — Segnaletica (4 slide) ⚠️ il modulo M2 del corso si
  chiama proprio "Segnaletica", quindi un cliente che scorre
  M3 "Diritti e doveri" e trova:
    54 Segnaletica di sicurezza in azienda
    62 Tipologie di segnaletica di sicurezza
    63 Esempi di segnaletica di sicurezza in officina
    64 Ruolo del dirigente per la segnaletica
  Pensa "perché Segnaletica è qui?". È deriva visibile.

  GRUPPO B — Procedimenti amministrativi (6 slide) ⚠️
    69 Sospensione dell'attività e somme aggiuntive
    70 Ricorso contro provvedimenti di sospensione
    73 Finanziamento della prevenzione
    74 Tempi e modalità di pagamento sanzioni
    75 Ispettorato nazionale del lavoro: funzioni
    76 Pagamento somme aggiuntive e revoca sospensione
  Sono procedure amministrative dell'ente di vigilanza, NON diritti
  del lavoratore.

  GRUPPO C — Tecniche/altre (3 slide) — meno gravi
    32 Verifiche periodiche negli impianti di sicurezza
    35 Documentazione per verifiche di sicurezza
    51 Formazione per esposizione a rischi da agenti fisici
    52 Dettagli formazione su rischi fisici
  Sono adiacenti-borderline ma non immediatamente OFF.

═══════════════════════════════════════════════════════════════════
DETTAGLIO 18 ON-TOPIC (per riferimento)
═══════════════════════════════════════════════════════════════════

  Doveri lavoratore (8):
    21 I principali doveri dei lavoratori
    22 Obbligo di non rimuovere i dispositivi di sicurezza
    23 Divieto di operazioni non autorizzate
    24 Partecipazione a formazione e addestramento obbligatori
    26 Segnalazione immediata di pericoli e difetti
    27 Uso corretto di attrezzature e sostanze pericolose
    40 Obblighi del lavoratore per la sicurezza
    56 Cosa devi fare con la formazione ricevuta

  Diritti lavoratore (4):
    10 Ruolo del rappresentante dei lavoratori per la sicurezza (RLS)
    4  Il datore di lavoro informa il RLS
    60 Ruolo del lavoratore nella segnaletica di sicurezza
    68 Importanza della collaborazione per la sicurezza

  Doveri datore di lavoro (6) — controparte dei diritti lavoratore:
    1  Obblighi formativi del datore di lavoro
    2  Formazione del datore di lavoro specializzato
    3  Riunione periodica: quando si convoca
    5  Corso formazione per datore di lavoro
    7  Riunione periodica sulla sicurezza
    31 Ruolo del datore di lavoro nelle verifiche di sicurezza

═══════════════════════════════════════════════════════════════════
GATE DI DECISIONE
═══════════════════════════════════════════════════════════════════

Lasciando da parte il "altro adiacente legittimo" (che hai
indicato come accettabile per Demo #2), la patologia residua è:

  - 32% ON-TOPIC
  - 18% formazione (legittimo)
  - 27% altro adiacente (legittimo)
  = 77% TOTALE accettabile
  + 23% OFF-TOPIC visibile

La soglia ROSSO che hai posto era "≥20% off-topic veri =
patologia leggera di Demo #3". Siamo al 23%, leggermente sopra.

Le 4 slide su "Segnaletica dentro Diritti e doveri" sono il
problema percepibile più grave perché Segnaletica È un modulo
SEPARATO del corso (M2), quindi il cliente vede chiaramente
duplicazione/sconfinamento.

═══════════════════════════════════════════════════════════════════
LA MIA PROPOSTA
═══════════════════════════════════════════════════════════════════

Demo #2 NON spedibile AS-IS — siamo appena sopra la tua soglia
ROSSO (23% vs 20%). I 13 off-topic sono visivamente identificabili
e raggruppano in 3 cluster di facile screenshot.

Tre opzioni:

OPZIONE 1 — Tengo Demo #2 in casa insieme a Demo #3, applico
  #31.8 A+B+C (la stessa cura), rigenero entrambi. Demo #2 dovrebbe
  beneficiare di B (M3 "Diritti e doveri" ha ricevuto 70 chunk
  con relevance ok, ma la dedup cosine ha probabilmente spinto le 4
  Segnaletica perché in M2 cosine ancora più alto MA top_k=70
  insufficiente → con A=67 a 4h ≈ pari + B+C il modulo M3 di
  Generale 4h dovrebbe ricevere chunk più on-topic).

OPZIONE 2 — Course Studio fix mirato: cancello manualmente le 13
  slide off-topic da Demo #2 (8 minuti via UI) → Demo #2 va al
  cliente OGGI con 69 slide M3 (anziché 82) tutte on-topic.
  Pro: nessun ritardo. Contro: M3 leggermente più corto (69 vs
  82), e il fix non risolve la pipeline (Demo successivi avranno
  lo stesso problema fino al #31.8).

OPZIONE 3 — Demo #2 va al cliente con caveat onesto ("M3 Diritti
  e doveri contiene 4 slide su segnaletica perché alcuni doveri
  riguardano l'osservanza della segnaletica — è una scelta
  pedagogica" — è onesto su 4 ma non sui 6 amministrativi
  ispettorato/sospensione). Mi sembra MENO onesto delle altre 2.

La mia propensione: OPZIONE 2 se vuoi ancora mandare 2 demo
oggi al cliente. OPZIONE 1 se accetti di tenere TUTTI E 3 fermi
e mandarli insieme rigenerati domani.

Domande:

DQ1. Quale opzione preferisci (1, 2, 3)?
DQ2. Se Opzione 1: Demo #1 (E25 Specifica 4h) lo mandi al cliente
     OGGI da solo o aspetti che siano tutti e 3 pronti?
DQ3. Se Opzione 2: confermi che 69 slide M3 invece di 82 è ok
     per la durata 4h (totale corso scende da 334 a 321, perdiamo
     ~5 min di durata sui 240 totali = 2% sotto)?
DQ4. In ogni caso, parto SUBITO con #31.8 A+B+C per Demo #3 e te
     lo mando rigenerato domani come deciso ieri review 11?

In attesa del tuo verdetto. Sto preparando in parallelo la
domanda strutturata sul deploy Vercel+Railway+GitHub+DevTools
che l'utente mi ha chiesto di mandarti (uscirà come messaggio
separato entro 30 min).

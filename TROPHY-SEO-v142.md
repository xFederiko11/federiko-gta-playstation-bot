# GTA VI — 55 schede trofei PS5 in italiano (v14.2)

## Fonti e accuratezza
- Fonte principale: https://www.powerpyx.com/gta-6-grand-theft-auto-vi-trophy-guide-roadmap/
- Elenco dei nomi PS5 in italiano: https://www.planetgta6.com/it/trofei-gta-6/
- Completamento 100% e medaglie Oro: https://www.powerpyx.com/gta-6-100-completion-checklist-guide/

Il catalogo versionato `trophies-gta6-v142.json` contiene 55 schede:
1 Platino, 2 Oro, 6 Argento, 46 Bronzo; 28 hidden/spoiler.
I requisiti sono riscritti in italiano e rimandano alla fonte. Quando il
testo originale non chiarisce la soluzione esatta, la scheda non inventa
passaggi o presunti glitch.

**Importante:** GTA VI non prevede medaglie Oro nelle missioni storia secondo
PowerPyx. Ci sono 2 trofei di grado Oro (finale storia e checklist 100%),
e medaglie Oro di attività diverse, ad esempio 42 prove nei poligoni di
tiro e 10 medaglie su 13 nelle sfide delle gare per il 100%.

## Pagine SEO
`build_trophy_site_v142.py` crea **55 pagine HTML individuali**, una
homepage con filtro spoiler, una pagina dedicata ai requisiti Oro,
sitemap.xml, robots.txt, title, description, link canonical, OG image,
Twitter cards e dati strutturati schema.org.

Indirizzo progettato:
https://xfederiko11.github.io/federiko-gta-playstation-bot/

La pubblicazione richiede **GitHub Pages abilitato su questo repository**:
1. GitHub → repository → **Settings → Pages**.
2. Impostare **Build and deployment → Source: GitHub Actions**.
3. Aprire **Actions → GTA VI - 55 Trofei SEO Pages v14.2** e avviare
   manualmente `Run workflow` se non parte da solo.
4. Attendere esito `deploy` e verificare una pagina, il sitemap e le foto.

Non dichiarare il sito indicizzato prima che sia accessibile. La richiesta di
indicizzazione a Google/Search Console richiede strumenti di proprietà del sito
e non è già stata eseguita. GitHub Pages pubblico è gratuito per repository
pubblici, senza nuovi abbonamenti.

## Foto, diritti e trofei nascosti

Ogni scheda presenta uno screenshot ufficiale **illustrativo** dal materiale
Rockstar già utilizzato nelle gallerie. Le tre immagini vengono riutilizzate
per categorie; NON sono foto di sblocco di ciascun trofeo, né immagini
proprietarie PowerPyx e non sono ridistribuite in un nuovo file. Il sito
attribuisce esplicitamente © Rockstar. Solo foto pertinenti e autorizzate
vanno usate in futuro per card esclusive.

Le 28 schede hidden sono mostrate sulla homepage soltanto in sezione
espandibile e hanno `noindex` finché non si imposta esplicitamente
`SPOILER_INDEX=1` in una build editoriale successiva.

## Serie automatica su X
- L'Autopilot esistente sceglie un trofeo **solo dopo** che il sito Pages
  risponde davvero con la homepage prevista.
- Massimo **2 post trofei al giorno** e almeno **160 minuti** fra i post
  della rubrica, usando lo stesso registro anti-duplicati editoriale.
- Partenza con trofeo Oro 100%, Platino, medaglie d'oro e consigli early-game.
- Trofei hidden non pubblicati prima del 21 novembre 2026 UTC.
- Ogni post ha testo italiano, emoji, requisiti, foto ufficiale illustrativa,
  link alla scheda SEO e hashtag; non copia guide o immagini PowerPyx.
- Fonte di verità: il ledger `.state/editorial-autopilot-v137.json`;
  mai cancellarlo o ritentare invii di esito incerto.

## Correzioni future
Aggiornare i requisiti solo verificandoli dopo nuove patch, salvare la
versione dell'informazione, testare e aprire PR. Non ripubblicare un
trofeo appena cambia il testo senza un controllo editoriale.

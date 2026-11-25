# Archivio patch autonomo — fase 1, 25 novembre 2026

La pagina ufficiale Launch Updates è consultabile tramite ricerca web, ma il monitor GitHub Actions continua a ricevere timeout. Non aggirare il servizio con proxy, credenziali, scraping aggressivo o abbonamenti.

- Riutilizzare esclusivamente l'HTML già acquisito con successo da support-gta6, con URL e titolo esatti. Nessuna richiesta HTTP aggiuntiva.
- Estrarre date e conteggi di voci da sezioni riconosciute. Conservare identificativo SHA-256 del contenuto, fonte, osservazioni e revisioni nel ledger history-public.json già persistente. Non copiare il testo originale o dedurre build/download.
- Formato imprevisto, fonte in errore o data futura: nessuna osservazione nuova. Conservare l'ultimo fatto e il reale errore monitor.
- Il riepilogo italiano del 23 novembre è già redatto sul sito. Il post evergreen lo presenta come archivio datato, non breaking; resta soggetto al limite esistente, pagina live e gate media.
- Fase 2: il sito consuma solo i record primari verificati di tipo official_patch_notes_available, mostra data, conteggio, fonte e data di osservazione in una sezione separata dai riepiloghi editoriali. Una revisione diversa segnala necessità di ricontrollo, non conferma automaticamente un testo italiano. La cronologia persistente rimane nel bot.
- Fase 3: preparare un riepilogo italiano originale solo da prove effettive e pubblicarlo tramite i normali test, canonical e cover condivisa. Nessuna news o correzione inventata in caso di indisponibilità.

La prima fase non dichiara il monitor ripristinato: i test sono fixture offline. Nessun costo, nuovo servizio o risposta automatica.

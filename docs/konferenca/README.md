# Gradivo za konferenco

Ta mapa vsebuje predstavitveno gradivo o uspešnosti modelov: grafe, zaslonske
posnetke aplikacije in zbirni dokument z razlagami.

Vse številke so prebrane neposredno iz zamrznjenih artefaktov v
[../../model_v3/outputs/](../../model_v3/outputs). Nobena vrednost ni prepisana
ročno; vsak graf v nogi navaja svojo izvorno datoteko.

## Vsebina

- [modelni-dokazi.html](modelni-dokazi.html): zbirni dokument z razlagami meril,
  validacijske zasnove, rezultatov in poštenih omejitev
- `grafi/`: devet grafov v PNG s **prosojnim ozadjem**, pripravljenih za prosojnice
- `grafi/za-temno-podlago/`: isti grafi s svetlo pisavo za temne prosojnice
- `zaslonski-posnetki/`: sedem posnetkov aplikacije v dvojni ločljivosti

Grafi v `grafi/` imajo temno pisavo in so namenjeni svetlim prosojnicam.

## Ponovno generiranje

Grafe generira `scripts/make_konferenca_charts.py`. Skripta prebere artefakte iz
`model_v3/outputs/` in zapiše obe barvni različici:

```bash
python scripts/make_konferenca_charts.py light
python scripts/make_konferenca_charts.py dark
```

Zaslonski posnetki so zajeti iz produkcijskega builda (`frontend/dist`) prek
`vite preview` in headless Chroma pri dvojni ločljivosti.

## Ključne številke

| Podatek | Vrednost |
|---|---|
| Enota analize | 212 občin × izdajni teden |
| Razvojne napovedi | 81.832 (osem časovnih razdelitev, 2017–2024) |
| Napovedi v zaklenjenem setu | 9.964 (leto 2025, ocenjeno enkrat) |
| MAE izbranega modela na zaklenjenem setu | 1,1688 |
| MAE primerjalnega GLM | 1,2183 |
| MAE preproste sezonske osnove | 1,2041 |

## Opozorilo pri uporabi

Pri predstavitvi je treba ohraniti tri poštena razkritja, ki so zapisana tudi v
dokumentu:

- preprosta sezonska osnova je pri RMSE boljša od izbranega modela
- prispevek vremena k napovedi ni dokazan; vremenska različica je v uporabi
  zaradi produktne zahteve, ne zaradi boljših rezultatov
- zaklenjeni set 2025 je bil odprt, zato je ocena retrospektivna revizija in ne
  nova neodvisna potrditev

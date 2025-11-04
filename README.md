# Minimize HTML

Nástroj pro analýzu a zmenšení (minifikaci) HTML souborů bez ztráty textového obsahu, případně s agresivním odstraněním nesdělovacích prvků.

## Požadavky
- Python 3.9+
- Windows PowerShell (příkazy níže)

## Instalace
Doporučeno použít existující virtuální prostředí `.venv/` v projektu.

```powershell
# z kořene projektu: C:\git\minimizeHtml
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Pokud virtuální prostředí ještě nemáte:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Rychlý start
Analyzujte, co zabírá místo v `00.html`:
```powershell
python minimize_html.py "00.html" --mode analyze
```
Typický výstup zahrnuje: původní velikost, odhad minifikované velikosti, bajty v komentářích, skriptech, stylech, inline stylech a data URI.

### Bezpečná minifikace (bez ztráty textu)
```powershell
python minimize_html.py "00.html" --mode minify -o "00.min.html"
```
- Odstraní komentáře a zbytečná bílá místa.
- Neodstraňuje obsahové prvky (text otázek/odpovědí zůstává 1:1).

#### Výchozí odstranění layoutových sloupců
- Ve výchozím stavu jsou z výsledku odstraněny prvky s klasami `reader_column left_column` a `reader_column right_column` (typické layoutové sloupce čtečky).
- Pokud je chcete zachovat, přidejte přepínač `--keep-reader-columns`.

Příklad ponechání sloupců v módu minify:
```powershell
python minimize_html.py "00.html" --mode minify --keep-reader-columns -o "00.min.keepcols.html"
```

### Agresivní odlehčení (ponechá text, odstraní nesdělovací prvky)
```powershell
# ponechá obrázky, ale vyčistí velká data URI
python minimize_html.py "00.html" --mode aggressive --keep-images -o "00.aggressive.html"

# zcela bez obrázků
python minimize_html.py "00.html" --mode aggressive -o "00.noimg.html"
```
Odstraní:
- `<script>`, `<style>`, `link rel=stylesheet/preload/preconnect`
- `iframe`, `embed`, `object`
- inline JS handlery (`onclick`, `onload`, …)
- komentáře

Chcete‑li v agresivním režimu zachovat informaci o zaškrtnutí odpovědí, použijte:
```powershell
python minimize_html.py "00.html" --mode aggressive --flatten-inputs --keep-images -o "00.aggressive.flat.html"
```
Tato volba nahradí `input type="checkbox"`/`radio` textovými značkami, např.:
- checkbox: `[x]` nebo `[ ]`
- radio: `(•)` nebo `( )`
Tak zůstane vidět, které odpovědi byly označené/správné, i bez CSS/JS.

Chcete‑li v agresivním režimu zachovat layoutové sloupce čtečky, použijte:
```powershell
python minimize_html.py "00.html" --mode aggressive --keep-reader-columns -o "00.aggressive.keepcols.html"
```

## Hromadné zpracování všech HTML v adresáři
Minifikace všech `.html` souborů:
```powershell
Get-ChildItem -File -Filter *.html | ForEach-Object {
  python minimize_html.py $_.FullName --mode minify
}
```
Agresivní varianta (ponechat obrázky):
```powershell
Get-ChildItem -File -Filter *.html | ForEach-Object {
  python minimize_html.py $_.FullName --mode aggressive --keep-images
}
```

## Poznámky
- Pro čisté zmenšení bez změny obsahu používejte `--mode minify`.
- Pokud vám stačí čistý text (např. otázky/odpovědi) a nepotřebujete skripty/styl, použijte `--mode aggressive`.
- Výstupní soubor lze určit `-o`. Pokud jej neuvedete, skript vytvoří soubor s příponou podle módu (např. `soubor.minify.html`).
- Výchozí chování: prvky s třídami `reader_column left_column` a `reader_column right_column` jsou odstraněny. Zachování vynutíte pomocí `--keep-reader-columns`.

## Soubory v projektu
- `minimize_html.py` – hlavní skript
- `requirements.txt` – závislosti
- `README.md` – tento návod

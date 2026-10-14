## Terminology Explanation

- quoting=csv.QUOTE_NONE (Ignorovanie úvodzoviek):

Bežné CSV formáty sa snažia obaľovať texty do úvodzoviek ("tento text"). Ak sa však v texte hry vyskytne jedna zabudnutá alebo neuzavretá úvodzovka, štandardný parser si myslí, že text pokračuje, a začne hltať všetko pod ním (stovky riadkov naraz).

Nastavenie QUOTE_NONE hovorí parseru: "Ignoruj úvodzovky úplne, nerieš ich." Hranice buniek sú dané výhradne tabulátormi a ničím iným.

- escapechar="\\" (Ochranný znak / spätná lomka):

Keďže ignorujeme úvodzovky a spoliehame sa na tabulátory, potrebujeme spôsob, ako ošetriť špeciálne znaky, ak by sa náhodou objavili tam, kde nemajú. Na to slúži escape charakter (\). Ak parser narazí na spätnú lomku, vie, že nasledujúci znak má brať doslovne a nie ako riadiaci príkaz formátu.

- Tu sú hlavné dôvody, prečo je random.uniform(2.5, 4.0) omnoho lepšia voľba než fixná pauza:

Ochrana pred detekciou botov (Behaviorálna analýza): Moderné anti-bot systémy nesledujú len IP adresy, ale analyzujú aj časové vzorce správania (tzv. timing patterns). Ak skript posiela požiadavky s chirurgickou presnosťou – napríklad presne každé 3,0 sekundy – pre systém je to okamžitý signál, že ide o stroj.

Simulácia ľudského správania: Žiadny človek neprechádza podstránky s rovnakou milisekundovou presnosťou. Raz vám chvíľu trvá, kým si niečo všimnete, inokedy prekliknete rýchlejšie. Náhodný rozptyl (raz 2.6 sekundy, inokedy 3.9 sekundy) verne napodobňuje ľudskú interakciu.

Bezpečnosť napriek CDP: Aj napriek tomu, že sa pripájate cez CDP k reálnemu Chromu, Cloudflare neustále vyhodnocuje frekvenciu požiadaviek. Náhodné pauzy pomáhajú efektívne rozbiť akýkoľvek detekovateľný rytmus.
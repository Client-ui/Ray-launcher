# Friend Aimbot (Fabric, 1.20.4)

Paprastas **kliento pusės** modas, kuris paspaudus `R` įjungia/išjungia automatinį taikymą į artimiausią žaidėją.

## ⚠️ Naudojimas
Skirta TIK privatiems serveriams, kur **visi žaidėjai žino ir sutinka**.
Viešuose serveriuose tai laikoma sukčiavimu ir už tai gausi banną.

## Diegimas
1. Įdiek [Fabric Loader](https://fabricmc.net/use/) ir Fabric API (1.20.4).
2. Į aplanką `mods` įmesk `.jar` iš `build/libs/`.

## Kompiliavimas
Reikia Java 17+ ir Gradle wrapper (jei jo nėra: `gradle wrapper`):
```
./gradlew build
```

## Nustatymai
`AimbotClient.java`:
- `RANGE` – taikymo nuotolis blokais
- `SMOOTHING` – sklandumas (1.0 = akimirksniu)

## Licencija
MIT

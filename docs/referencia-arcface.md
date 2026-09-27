# Reconocimiento facial (ArcFace + SCRFD en Hailo-8) — referencia

Referencia práctica de qué hace, qué reconoce, qué no, y cómo interpretarlo. Basado en el
setup real del depto: FaceEmbed API de Seeed corriendo en el Hailo-8 (ver
[`estado-actual.md`](estado-actual.md), servicio `face-embed`).

## Cómo funciona (el pipeline)

```
cámara → SCRFD (detección)     → encuentra caras + 5 landmarks (ojos, nariz, boca)
       → alineación            → rota/recorta la cara a una pose canónica
       → ArcFace (MobileFaceNet) → embedding: vector de 512 números, normalizado (L2)
       → similitud coseno      → compara el vector contra los enrolados
```

- **El embedding NO es una foto.** Es una "huella" numérica de 512 dimensiones. Dos fotos de
  la misma persona producen vectores parecidos; de personas distintas, vectores lejanos.
- **La comparación es similitud coseno**: un número. Más alto = más parecido.
- **ArcFace** (Additive Angular Margin) es el modelo entrenado para que las caras de la misma
  persona queden juntas y las de distintas, separadas. Es el estándar de la industria.

## La escala de similitud (lo que medimos acá)

| Similitud | Interpretación |
|---|---|
| **> 0.6** | Match muy confiable (misma persona, buena captura) |
| **0.45 – 0.6** | Match confiable — **nuestro threshold operativo: 0.45** |
| **0.3 – 0.45** | Zona gris: probablemente la misma persona pero captura pobre |
| **< 0.3** | No-match (o captura mala de la persona correcta) |

Medición real en el depto:
- **1 sola foto enrolada** → reconocimiento dio **0.27** (quedó bajo el threshold, "no reconocido").
- **6 fotos enroladas** (variando pose, con y sin lentes) → subió a **0.82**. 

**Lección clave: enrolar varias tomas variadas es lo que hace robusto al sistema.** Con una
sola foto, cualquier cambio de luz/ángulo tira el score abajo.

## Qué reconoce BIEN

- La misma persona en **distintas poses moderadas** (hasta ~30-40° de giro) si enrolaste variedad.
- **Con y sin anteojos** — si enrolaste ambos casos (lo probamos: te reconoce con lentes).
- Cambios de **iluminación** razonables.
- Peinados distintos, con/sin gorra (si la cara se ve).
- Distintas expresiones (sonrisa, seria).

## Qué reconoce MAL o NO reconoce

- **Caras muy de perfil** (>45°): SCRFD puede ni detectarlas, y el embedding se degrada.
- **Lejos / baja resolución**: si la cara ocupa pocos píxeles (< ~80px), el embedding es pobre.
  Regla práctica: la cara tiene que "llenar" bien el recuadro.
- **Poca luz, contraluz, movimiento (blur)**: bajan mucho el score. La webcam USB es sensible a esto.
- **Oclusiones fuertes**: barbijo, mano en la cara, bufanda tapando media cara.
- **Cambios drásticos con el tiempo**: barba nueva/afeitada, mucho peso, años. Conviene re-enrolar.
- **Gemelos idénticos**: ArcFace puede confundirlos (son casi idénticos para el modelo).
- **Una cara no enrolada**: da similitud baja contra todos → cae como "desconocido" (correcto).

## Límite crítico de seguridad ⚠️

**ArcFace NO tiene detección de vida (liveness).** Reconoce la cara en la imagen, sin saber si
es una persona real o una **foto / pantalla / video** de esa persona. Se puede engañar
mostrándole una foto tuya en un celular.

**Consecuencia:** face rec sirve para **contexto y automatización** (saber quién parece estar,
notificar, prender luces), **NUNCA para seguridad** (abrir la cerradura, desarmar alarma). Esto
es coherente con la spec del proyecto (§seguridad de la cerradura: "sensores → escenas, nunca
unlock automático"). El reconocimiento facial es una señal *blanda*, no una credencial.

## Falsos positivos vs falsos negativos (el threshold)

- **Threshold alto** (ej. 0.6): menos falsos positivos (no confunde a un desconocido con vos),
  pero más falsos negativos (a veces no te reconoce en una captura mala).
- **Threshold bajo** (ej. 0.3): te reconoce casi siempre, pero riesgo de marcar a un
  desconocido como vos.
- **Nuestro 0.45**: balance. Con la galería multi-toma, vos das ~0.8 (pasa cómodo) y un
  desconocido raramente supera 0.45.

## Tips para mejorar el reconocimiento

1. **Enrolá 5-10 tomas** variando pose, luz, con/sin lentes, expresión.
2. Buena luz frontal, cara ocupando buena parte del cuadro, sin movimiento.
3. Re-enrolá si cambiás mucho de aspecto (barba, corte).
4. Si hay falsos positivos con visitas, subí el threshold; si no te reconoce, bajalo o enrolá más.
5. La cámara USB es de laboratorio — una cámara fija bien ubicada e iluminada (ej. la PoE de la
   entrada, Fase 4) da resultados mucho más estables.

## Rendimiento

- Embedding en **~11 ms** por cara en el Hailo-8 (SCRFD + ArcFace). Sobra para tiempo real.
- El Hailo hace el trabajo pesado; la CPU de la Pi queda libre.

## Privacidad

- Los embeddings son **datos biométricos**: se guardan en `face-embed/data/vectors.db` (SQLite,
  local, en la R2130, incluido en el backup — fuera de git).
- Todo corre **local** (Hailo + SQLite). Nada se envía a la nube.
- Es tu depto y tu cara; aun así, tenerlo consciente: si enrolás a otras personas, es su dato
  biométrico.

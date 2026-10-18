# Echo Dot 2 → EchoLocal → Home Assistant

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15594/badge)](https://www.bestpractices.dev/projects/15594)

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Este documento es una introducción traducida con una ruta de inicio. Las instrucciones detalladas y los comandos se mantienen por ahora en inglés y están enlazados abajo. El idioma del README no cambia el reconocimiento, la voz de respuesta ni la frase de activación.

Este proyecto documenta cómo convertir un **Echo Dot de segunda generación (RS03QR, BISCUIT)** existente en un satélite de voz de Home Assistant con **EchoLocal**. Incluye instrucciones, herramientas del host USB y etapas reproducibles para entrenar y evaluar una frase de activación. No incluye firmware, grabaciones, modelos entrenados ni credenciales.

![Echo Dot 2 → EchoLocal → Home Assistant](docs/assets/architecture.svg)

## Primeros pasos

1. Identifique el modelo con la [guía de hardware](docs/hardware-compatibility.md) y confirme BISCUIT por USB. Una entrada llamada «Echo» en HA no demuestra compatibilidad.
2. Prepare un host USB Linux, alimentación estable y un cable de datos. La ruta probada utiliza un contenedor en Synology; siga la [guía ordenada](docs/runbook.md).
3. Ejecute la [conversión](research/conversion.md) por etapas: desbloqueo, TWRP, copia verificada después del desbloqueo y versiones compatibles de Fire OS y EchoLocal. USB se usa para estas operaciones y para recuperación.
4. Configure en HA la integración **ESPHome** y un **pipeline de Assist** con reconocimiento de voz, agente de conversación y síntesis. Seleccione el idioma y empareje el dispositivo con su clave. Compruebe TCP 6053 y las direcciones multimedia según la [guía de HA](research/ha-integration.md).
5. Compruebe voz normal, respuesta, reinicio y funcionamiento prolongado con el [plan de aceptación](docs/acceptance-and-batch.md). Tras convertirlo, el Dot funciona por Wi-Fi y alimentación normal; no necesita una conexión USB de datos permanente.

## Límites y validación

El resultado del 2 de octubre de 2026 es una prueba histórica de EchoLocal 0.0.8, no una garantía del estado actual ni de todas las versiones. Las frases «Привет, Мышка» y «Привет, котик» siguen siendo experimentales: las métricas sintéticas no prueban fiabilidad en una habitación real. No use imágenes de Dot 2 en un Echo de tamaño completo, Show u otra generación de Dot. HACS, Music Assistant y ESPHome Device Builder no son necesarios para la voz básica. Un pipeline con servicios en la nube sigue necesitando conexión de red.

## Documentación detallada

- [Índice](docs/README.md)
- [Entrenamiento y grabación](training/README.md)
- [Acceso al dispositivo](docs/device-access.md)
- [Controles y límites](docs/device-controls.md)
- [Música](docs/music-latency.md)
- [Registro de validación](docs/operations-findings.md)
- [Seguridad](SECURITY.md)
- [Publicación y versiones](docs/publication.md)
- [Contribuciones y traducción](docs/i18n.md)

## Proyectos relacionados

- [EchoMuse / emOS](https://github.com/ha-homelab/ha-echomuse)
- [Echo Show 5 / Android](https://github.com/ha-homelab/ha-echo-show-5)
- [Amazon Echo Home Energy / Alexa](https://github.com/4alvit/amazon-echo-home-voice)

EchoMuse con emOS es otra plataforma de software para Dot. Su configuración, acceso y recuperación se documentan en su propio repositorio. El proyecto Alexa conserva la plataforma original; no la convierte en un satélite Assist.

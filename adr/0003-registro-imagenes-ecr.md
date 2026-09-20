# ADR-0003: Estrategia de registro y gestión de imágenes de contenedor

## Estado
Aceptada, 17 de septiembre de 2026

## Contexto
Los microservicios Usuarios y Pagos (ADR-0001) se conteneriza en Docker y se
despliegan como tareas de ECS Fargate (ADR-0002). Se necesita definir dónde y
cómo se almacenan y versionan las imágenes de contenedor antes de que ECS pueda
consumirlas, incluyendo la organización de repositorios, la convención de tags
y qué sucede con imágenes obsoletas dentro del entorno de Learner Lab.

## Decisión
Se utiliza **Amazon ECR (Elastic Container Registry)** con **un repositorio
privado por microservicio**:

- `micropay/usuarios`
- `micropay/pagos`

Convenciones aplicadas:
- **Tagging**: cada imagen se etiqueta con el nombre corto del commit de Git
  (ej. `usuarios:a1b2c3d`) además del tag `latest`, de forma que cada despliegue
  en ECS quede trazado a una versión específica del código y no dependa
  únicamente de `latest`.
- **Escaneo de vulnerabilidades**: se activa *Scan on push* (escaneo básico
  gratuito de ECR) en ambos repositorios, para detectar CVEs conocidos en las
  imágenes antes de desplegarlas.
- **Ciclo de vida (lifecycle policy)**: se configura una política simple que
  conserva las últimas 5 imágenes etiquetadas y elimina automáticamente el
  resto, evitando acumulación innecesaria de artefactos durante las iteraciones
  de prueba.
- **Permisos**: `LabRole` (rol de ejecución de las tareas ECS) requiere permisos
  `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage` y `ecr:GetAuthorizationToken`
  para poder hacer *pull* de las imágenes al arrancar cada tarea — se valida que
  `LabRole` ya cubre estos permisos por defecto en Learner Lab.
- **Escaneo de vulnerabilidades**: activado como **Basic scanning** a nivel
  de registro (Amazon ECR deprecó la configuración de *scan on push* por
  repositorio individual), con un filtro `micropay/*` que cubre ambos
  repositorios del proyecto.

## Alternativas consideradas

| Alternativa | Por qué se descarta |
|---|---|
| Un único repositorio ECR compartido, diferenciando servicios por prefijo de tag (ej. `micropay:usuarios-latest`) | Mezcla el ciclo de vida de imágenes de ambos servicios en un mismo repositorio, dificultando aplicar políticas de retención o escaneo diferenciadas por servicio, y contradice la independencia de despliegue definida en ADR-0001 |
| Docker Hub (registro público externo) | Introduce una dependencia externa fuera del ecosistema AWS, sin la integración nativa de IAM y sin el escaneo de vulnerabilidades integrado que sí ofrece ECR |
| Solo tag `latest`, sin versión por commit | No permite hacer rollback a una versión anterior conocida ni trazar qué código específico corresponde a la imagen desplegada en un momento dado |

## Consecuencias

**Positivas**
- Cada microservicio tiene su propio historial de imágenes, alineado con su
  propio ciclo de despliegue independiente (ADR-0001).
- La trazabilidad por commit permite identificar exactamente qué versión del
  código está corriendo en ECS en un momento dado, y facilita el rollback si
  una imagen introduce un defecto.
- El escaneo automático agrega una capa básica de seguridad sin esfuerzo
  operativo adicional.

**Negativas / trade-offs**
- Dos repositorios en vez de uno implican el doble de configuración inicial
  (políticas de ciclo de vida y permisos aplicados dos veces).
- El escaneo *Scan on push* añade algunos segundos de latencia al finalizar
  cada `docker push`, antes de que la imagen quede disponible para su consumo.

## Alineación con AWS Well-Architected Framework
- **Security**: repositorios privados con control de acceso IAM y escaneo de
  vulnerabilidades integrado antes del despliegue.
- **Operational Excellence**: trazabilidad de versiones por commit facilita
  diagnóstico y rollback ante incidentes.
- **Cost Optimization**: la política de ciclo de vida evita acumulación de
  imágenes no utilizadas, que de otro modo generarían costo de almacenamiento
  indefinido.

## Brecha entre diseño ideal y AWS Academy Learner Lab
- **Ideal**: pipeline de CI/CD (ej. GitHub Actions o AWS CodePipeline) que
  construya, escanee y publique la imagen en ECR automáticamente en cada push
  a la rama principal, disparando además el despliegue en ECS.
- **Esta iteración**: el build y push de imágenes se realiza de forma manual
  desde la línea de comandos (`docker build` + `docker push` autenticado vía
  `aws ecr get-login-password`), dado que el alcance de la evaluación no exige
  automatización de CI/CD y el tiempo de sesión en Learner Lab es limitado. Se
  documenta como evolución futura del proyecto.
- No se identifican restricciones adicionales del Learner Lab que afecten
  específicamente a ECR (a diferencia de IAM o SSH en otros servicios).

## RTO/RPO objetivo
- No aplica directamente a ECR: el registro de imágenes es un artefacto de
  build, no un componente en el camino crítico de disponibilidad en tiempo de
  ejecución. Si ECR estuviera temporalmente inaccesible, los servicios ya
  desplegados en ECS continúan operando con las tareas ya iniciadas.

## Costo
Amazon ECR incluye 500 MB-mes de almacenamiento gratuito en el Free Tier (12
meses), independiente del crédito del Learner Lab. Dado el tamaño reducido de
las imágenes de este proyecto (servicios simples) y la política de retención de
5 imágenes por repositorio, se espera permanecer dentro de ese margen gratuito
durante toda la duración de la evaluación.

## Referencias
- Amazon ECR - Documentación oficial
- Amazon ECR - Image scanning
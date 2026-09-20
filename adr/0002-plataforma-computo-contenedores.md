# ADR-0002: Selección de plataforma de cómputo para los microservicios

## Estado
Aceptada, 17 de septiembre de 2026

## Contexto
En ADR-0001 se definió la descomposición del dominio en dos microservicios
independientes (Usuarios, Pagos), cada uno contenerizado en Docker. Se necesita
ahora una plataforma de cómputo que ejecute esos contenedores cumpliendo:

- Orquestación de contenedores sin gestión manual de servidores.
- Independencia de despliegue y escalado por servicio.
- Integración nativa con Amazon ECR, CloudWatch Logs y API Gateway.
- Operación dentro del presupuesto de crédito gratuito de AWS Academy Learner Lab.
- Restricciones ya conocidas del entorno: `iam:CreateRole` bloqueado (se usa
  `LabRole`), sin acceso SSH a instancias.

## Decisión
Se ejecutan ambos microservicios en **Amazon ECS con el modo de lanzamiento
Fargate**, dentro de un único clúster ECS (`micropay-cluster`) que aloja dos
Services independientes, uno por microservicio, cada uno con su propia Task
Definition.

Configuración base por servicio:
- **Task Definition** con tamaño mínimo viable: 0.25 vCPU / 0.5 GB de memoria.
- **Modo de red** `awsvpc`: cada tarea recibe su propia interfaz de red (ENI)
  y Security Group dentro de la VPC.
- **Rol de ejecución y rol de tarea**: `LabRole` (no se puede crear un rol IAM
  dedicado en Learner Lab).
- **Ubicación de red**: cada tarea se despliega en la subred privada de
  **cualquiera de las dos Availability Zones** (`us-east-1a`, `us-east-1b`)
  configuradas en el `awsvpcConfiguration` del Service, ECS distribuye las
  tareas entre ambas AZ.
- **Desired count**: 2 tareas por servicio como línea base (1 por AZ como
  piso mínimo de disponibilidad real).
- **Logging**: driver `awslogs`, enviando stdout/stderr de cada contenedor a
  su propio log group en CloudWatch (detalle en ADR-0005).

Adicionalmente, se configura **Service Auto Scaling** (Application Auto
Scaling) sobre cada ECS Service:

- **Recurso escalable**: `service/micropay-cluster/<nombre-del-servicio>`.
- **Dimensión**: `ecs:service:DesiredCount`.
- **Capacidad**: mínimo 2 tareas, máximo 4 tareas por servicio (manteniendo
  al menos 1 tarea saludable por AZ incluso en el piso mínimo, requisito
  para que el ALB tenga siempre un target por zona, ver ADR-0004).
- **Política**: Target Tracking sobre `ECSServiceAverageCPUUtilization`,
  con umbral objetivo de 60%.
- **Cooldown**: 60 segundos tanto para scale-out como para scale-in.

Un solo clúster para ambos servicios porque en Fargate el clúster es solo
una agrupación lógica sin costo propio, el costo real está en las tareas.

## Alternativas consideradas

| Alternativa | Por qué se descarta |
|---|---|
| ECS con EC2 launch type | Requiere aprovisionar y parchear instancias manualmente; contradice el objetivo de reducir carga operativa |
| Amazon EKS | Complejidad operativa alta y costo fijo del control plane no alineado con un entorno educativo de crédito limitado |
| AWS Lambda detrás de API Gateway (sin contenedores) | No cumple el requerimiento explícito de contenerizar en Docker y desplegar en ECS Fargate |

## Consecuencias

**Positivas**
- Cero servidores que parchear o dimensionar.
- Cada microservicio escala su propio número de tareas de forma dinámica e
  independiente, respondiendo a su carga real de CPU.
- ECS reemplaza automáticamente tareas que fallan el *health check*.
- El modo `awsvpc` permite aplicar Security Groups distintos por servicio.
- Con al menos una tarea por AZ en todo momento, una falla completa de una
  Availability Zone no interrumpe el servicio: el ALB (ADR-0004) deja de
  enrutar hacia la AZ afectada y sigue sirviendo desde la AZ saludable.

**Negativas / trade-offs**
- Complejidad adicional de configuración (recurso escalable + política de
  target tracking por servicio).
- Bajo carga sostenida, el servicio puede escalar hasta 4 tareas
  simultáneas (2 por AZ), incrementando el consumo de crédito — aceptable
  porque el clúster se elimina al finalizar la sesión de laboratorio.
- Se introduce una llamada de red real entre servicios (vs. llamada en
  memoria del monolito).

## Alineación con AWS Well-Architected Framework
- **Operational Excellence**: sin gestión de servidores ni parches del
  sistema operativo subyacente.
- **Reliability**: reemplazo automático de tareas no saludables, y
  tolerancia a la pérdida completa de una Availability Zone gracias a
  mantener al menos una tarea sana por zona en todo momento.
- **Performance Efficiency**: capacidad de cómputo ajustada dinámicamente
  por servicio mediante Auto Scaling basado en CPU.
- **Security**: aislamiento de red por tarea vía `awsvpc` y Security Groups
  dedicados.
- **Cost Optimization**: se paga solo por los recursos asignados mientras
  la tarea está activa.

## Brecha entre diseño ideal y AWS Academy Learner Lab
- **Ideal**: distribución de tareas en múltiples Availability Zones — ya
  implementada en esta iteración, más el uso de Fargate Spot para cargas
  no críticas.
- **Esta iteración**: la distribución multi-AZ se incorporó al diseño base
  tras identificar que un Application Load Balancer no puede aprovisionarse
  con subredes de una sola Availability Zone, requisito técnico de AWS,
  no una optimización opcional (ver ADR-0004). Fargate Spot queda fuera de
  alcance por simplicidad de la demostración.
- Ubicación de las tareas y su relación con NAT Gateway (uno por AZ) se
  resuelve en ADR-0004.

## RTO/RPO objetivo
- **RTO**: < 5 minutos — health check de ECS, reemplazo automático de
  tareas, y tolerancia a la pérdida completa de una AZ.
- **RPO**: No aplica — los servicios no persisten datos (ADR-0001).

## Costo
Con la línea base corregida a 2 tareas por servicio (1 por AZ) y Auto
Scaling hasta 4, el costo de cómputo en reposo se duplica respecto a una
configuración de una sola AZ. Se acepta este incremento porque la
disponibilidad real ante falla de zona es uno de los objetivos explícitos
de la evaluación, y porque el clúster se elimina al finalizar la sesión de
laboratorio. Verificar el rango con la AWS Pricing Calculator.

## Referencias
- Amazon ECS - Documentación oficial (Fargate launch type)
- AWS Well-Architected Framework - Reliability y Cost Optimization Pillars
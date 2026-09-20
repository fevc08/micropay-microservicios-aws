# Microservicio: Pagos

## Responsabilidad
Procesamiento y consulta de transacciones de pago.

## Contrato de exposición
- **Ruta pública** (vía API Gateway): `/pagos`
- **Puerto interno del contenedor**: 8080 (placeholder, ajustar según la
  implementación real del servicio)
- **Health check**: `/pagos/health` (usado por el target group del ALB
  dedicado a este servicio)

## Imagen de contenedor
- **Repositorio ECR**: `micropay/pagos`
- **Convención de tag**: hash corto del commit de Git (ej. `d4e5f6a`)
- **Build**: manual, desde Docker CLI local (ver ADR-0003)

## Infraestructura asociada
- ECS Service dedicado en el clúster `micropay-cluster`, con Auto Scaling
  (1-3 tareas), ver ADR-0002.
- Application Load Balancer dedicado en subred pública, target group
  apuntando a las tareas de este servicio en subred privada, ver ADR-0004.
- Log group de CloudWatch: `/ecs/micropay/pagos`, ver ADR-0005.

## Pendiente de implementación
Esta carpeta representa el lugar donde vivirá el código fuente y el
`Dockerfile` de este microservicio cuando se desarrolle la implementación.
Por ahora documenta el contrato del servicio dentro de la arquitectura.
SELECT
    COALESCE(cerrados.tecnico_asignado, recibidos.tecnico_asignado) AS tecnico_asignado,
    COALESCE(recibidos.total_tickets_del_mes, 0) AS Cant_tickets_recibidos,
    COUNT(DISTINCT cerrados.ticket_id) AS total_tickets_cerrados,  -- Lógica clave aquí
    COALESCE(SUM(cerrados.Cant_tickets_cerrados_con_SLA), 0) AS Cant_tickets_cerrados_con_SLA,
    COALESCE(SUM(cerrados.Cant_tickets_cerrados_dentro_SLA), 0) AS Cant_tickets_cerrados_dentro_SLA,
    ROUND(100 * COALESCE(SUM(cerrados.Cant_tickets_cerrados_con_SLA), 0) / NULLIF(COUNT(DISTINCT cerrados.ticket_id), 0), 2) AS porcentaje_fuera_del_plazo,
    ROUND(100 * COALESCE(SUM(cerrados.Cant_tickets_cerrados_dentro_SLA), 0) / NULLIF(COUNT(DISTINCT cerrados.ticket_id), 0), 2) AS porcentaje_en_plazo,
    COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) AS cuenta_de_tickets_reabiertos
FROM (
    -- Subconsulta base para tickets recibidos (sin cambios)
    SELECT
        CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
        COUNT(DISTINCT gt.id) AS total_tickets_del_mes
    FROM
        glpi_tickets gt
    JOIN glpi_entities ge ON gt.entities_id = ge.id
    JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
    JOIN glpi_users gu ON t_users_tec.users_id = gu.id
    WHERE
        gt.is_deleted = 0
        AND ge.completename IS NOT NULL
        AND LOCATE('@', ge.completename) = 0
        AND LOCATE('CASOS DUPLICADOS', UPPER(ge.completename)) = 0
        AND gt.date BETWEEN CONVERT_TZ('2024-12-01', 'America/Caracas', 'UTC')
                        AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
        #{tecnicos_condicion}
    GROUP BY
        tecnico_asignado
) AS recibidos
LEFT JOIN (
    -- Subconsulta modificada para emular COUNT(DISTINCT ticket_id) del query original
    SELECT
        CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
        gt.id AS ticket_id,  -- Incluir ticket_id para contar distinto
        CASE
            WHEN gt.time_to_resolve IS NOT NULL THEN 1
            ELSE 0
        END AS Cant_tickets_cerrados_con_SLA,
        CASE
            WHEN gt.solvedate <= gt.time_to_resolve THEN 1
            ELSE 0
        END AS Cant_tickets_cerrados_dentro_SLA
    FROM
        glpi_tickets gt
    JOIN glpi_entities ge ON gt.entities_id = ge.id
    JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
    JOIN glpi_users gu ON t_users_tec.users_id = gu.id
    WHERE
        gt.is_deleted = 0
        AND gt.status > 4
        AND gt.solvedate BETWEEN CONVERT_TZ('2024-12-01', 'America/Caracas', 'UTC')
                            AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
        AND ge.completename IS NOT NULL
        AND LOCATE('@', ge.completename) = 0
        AND LOCATE('CASOS DUPLICADOS', UPPER(ge.completename)) = 0
        #{tecnicos_condicion}
) AS cerrados ON recibidos.tecnico_asignado = cerrados.tecnico_asignado
LEFT JOIN (
    -- Subconsulta para tickets reabiertos (sin cambios)
    SELECT
        CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
        COUNT(DISTINCT gi.items_id) AS cuenta_de_tickets_reabiertos
    FROM
        glpi_itilsolutions gi
    INNER JOIN glpi_tickets gt ON gi.items_id = gt.id
    INNER JOIN glpi_users gu ON gi.users_id = gu.id
    WHERE
        gi.status = 4
        AND gi.users_id_approval > 0
        AND CONVERT_TZ(gi.date_approval, 'UTC', 'America/Caracas') BETWEEN '2024-12-01' AND '2024-12-31 23:59:59'
    GROUP BY
        tecnico_asignado
) AS reabiertos ON recibidos.tecnico_asignado = reabiertos.tecnico_asignado
GROUP BY
    recibidos.tecnico_asignado
ORDER BY
    tecnico_asignado;
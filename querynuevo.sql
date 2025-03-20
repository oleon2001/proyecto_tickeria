SELECT
    recibidos.tecnico_asignado,
    COALESCE(cerrados_sla.Cant_tickets_cerrados_dentro_SLA, 0) AS Cant_tickets_cerrados_dentro_SLA,
    COALESCE(cerrados_sla.Cant_tickets_cerrados_con_SLA, 0) AS Cant_tickets_cerrados_con_SLA,
    COALESCE(pendientes_sla.tickets_pendientes_SLA, 0) AS tickets_pendientes_SLA,
    CASE 
        WHEN (COALESCE(cerrados_sla.Cant_tickets_cerrados_con_SLA, 0) + COALESCE(pendientes_sla.tickets_pendientes_SLA, 0)) = 0 THEN 0 
        ELSE ROUND(
            (COALESCE(cerrados_sla.Cant_tickets_cerrados_dentro_SLA, 0) / 
            (COALESCE(cerrados_sla.Cant_tickets_cerrados_con_SLA, 0) + COALESCE(pendientes_sla.tickets_pendientes_SLA, 0))) * 100, 
            2
        ) 
    END AS `Cumplimiento SLA`,
    COALESCE(cerrados_count.total_tickets_cerrados, 0) AS Cant_tickets_cerrados,
    COALESCE(recibidos.total_tickets_del_mes, 0) AS Cant_tickets_recibidos,
    CASE 
        WHEN COALESCE(cerrados_count.total_tickets_cerrados, 0) = 0 THEN 0 
        ELSE ROUND((COALESCE(cerrados_count.total_tickets_cerrados, 0) / COALESCE(recibidos.total_tickets_del_mes, 0)) * 100, 2) 
    END AS `CumplimientoTR/TC`,
    COALESCE(reabiertos.cuenta_de_tickets_reabiertos, 0) AS cuenta_de_tickets_reabiertos
            FROM (
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
                    AND gt.date BETWEEN CONVERT_TZ('2024-12-01 00:00:00', 'America/Caracas', 'UTC')
                                    AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
                   # {tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS recibidos
            LEFT JOIN (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    COUNT(DISTINCT gt.id) AS total_tickets_cerrados
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                WHERE
                    gt.is_deleted = 0
                    AND gt.status > 4
                    AND gt.solvedate BETWEEN CONVERT_TZ('2024-12-01 00:00:00', 'America/Caracas', 'UTC')
                                        AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
                    AND gt.date BETWEEN CONVERT_TZ('2024-12-01 00:00:00', 'America/Caracas', 'UTC')
                                    AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
                    #{tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS cerrados_count ON recibidos.tecnico_asignado = cerrados_count.tecnico_asignado
            LEFT JOIN (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    SUM(CASE WHEN gt.time_to_resolve IS NOT NULL THEN 1 ELSE 0 END) AS Cant_tickets_cerrados_con_SLA,
                    SUM(CASE WHEN gt.solvedate < gt.time_to_resolve THEN 1 ELSE 0 END) AS Cant_tickets_cerrados_dentro_SLA
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                WHERE
                    gt.is_deleted = 0
                    AND gt.status >= 4
                    AND gt.solvedate BETWEEN CONVERT_TZ('2024-12-01 00:00:00', 'America/Caracas', 'UTC')
                                        AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
                    #{tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS cerrados_sla ON recibidos.tecnico_asignado = cerrados_sla.tecnico_asignado
            LEFT JOIN (
                SELECT
                    CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
                    COUNT(DISTINCT gt.id) AS cuenta_de_tickets_meses_anteriores
                FROM
                    glpi_tickets gt
                JOIN glpi_entities ge ON gt.entities_id = ge.id
                JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
                JOIN glpi_users gu ON t_users_tec.users_id = gu.id
                WHERE
                    gt.is_deleted = 0
                    AND gt.status >= 4
                    AND gt.solvedate BETWEEN CONVERT_TZ('2024-12-01 00:00:00', 'America/Caracas', 'UTC')
                                        AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
                    AND gt.date < CONVERT_TZ('2024-12-01 00:00:00', 'America/Caracas', 'UTC')
                    #{tecnicos_condicion}
                GROUP BY tecnico_asignado
            ) AS abierto_meses_anteriores  ON recibidos.tecnico_asignado = abierto_meses_anteriores.tecnico_asignado
            LEFT JOIN (
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
                    AND CONVERT_TZ(gi.date_approval, 'UTC', 'America/Caracas') BETWEEN '2024-12-01 00:00:00' AND '2024-12-31 23:59:59'
                GROUP BY tecnico_asignado
            ) AS reabiertos ON recibidos.tecnico_asignado = reabiertos.tecnico_asignado
            LEFT JOIN (
    SELECT 
        CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
        COUNT(DISTINCT gt.id) AS tickets_pendientes_SLA
    FROM
        glpi_tickets gt
    JOIN glpi_entities ge ON gt.entities_id = ge.id
    JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
    JOIN glpi_users gu ON t_users_tec.users_id = gu.id
    WHERE
        gt.is_deleted = 0
        AND gt.status > 4
        AND gt.date BETWEEN CONVERT_TZ('2024-12-01', 'America/Caracas', 'UTC')
                        AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
        AND gt.solvedate > CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
        AND gt.time_to_resolve < CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
    GROUP BY tecnico_asignado
) AS pendientes_sla ON recibidos.tecnico_asignado = pendientes_sla.tecnico_asignado
            ORDER BY recibidos.tecnico_asignado;

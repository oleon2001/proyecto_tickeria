SELECT 
        CONCAT(gu.realname, ' ', gu.firstname) AS tecnico_asignado,
        COUNT(DISTINCT gt.id)
        #COUNT(DISTINCT gt.id) AS `tickets_pendientes_SLA`
    FROM
        glpi_tickets gt
    JOIN glpi_entities ge ON gt.entities_id = ge.id
    JOIN glpi_tickets_users t_users_tec ON gt.id = t_users_tec.tickets_id AND t_users_tec.type = 2
    JOIN glpi_users gu ON t_users_tec.users_id = gu.id
    WHERE
        gt.is_deleted = 0
        AND gt.status >= 4
        AND gt.date BETWEEN CONVERT_TZ('2024-12-01', 'America/Caracas', 'UTC')
                        AND CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
        AND gt.solvedate > CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
        AND gt.time_to_resolve < CONVERT_TZ('2024-12-31 23:59:59', 'America/Caracas', 'UTC')
        group by tecnico_asignado
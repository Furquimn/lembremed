from django.http import JsonResponse
from django.contrib.auth.decorators import permission_required
from django.db import connection
import pandas as pd

@permission_required('lembremed.pode_gerenciar_profissional')
def heatmap_data(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN EXTRACT(HOUR FROM h.hora) BETWEEN 0 AND 5 THEN 'Madrugada (0h-5h)'
                        WHEN EXTRACT(HOUR FROM h.hora) BETWEEN 6 AND 11 THEN 'Manhã (6h-11h)'
                        WHEN EXTRACT(HOUR FROM h.hora) BETWEEN 12 AND 17 THEN 'Tarde (12h-17h)'
                        WHEN EXTRACT(HOUR FROM h.hora) BETWEEN 18 AND 23 THEN 'Noite (18h-23h)'
                    END as turno,
                    CASE
                        WHEN a.dthr_administracao IS NULL THEN 'Não Administrado'
                        WHEN EXTRACT(HOUR FROM a.dthr_administracao) > h.hora THEN 'Atraso'
                        WHEN EXTRACT(HOUR FROM a.dthr_administracao) < h.hora THEN 'Antecipado'
                        ELSE 'No Horário'
                    END as tipo_erro,
                    COUNT(*) as contagem
                FROM lembremed_administra a
                JOIN lembremed_horario h ON h.codigo = a.horario_id
                GROUP BY turno, tipo_erro
                ORDER BY 
                    CASE 
                        WHEN turno = 'Madrugada (0h-5h)' THEN 1
                        WHEN turno = 'Manhã (6h-11h)' THEN 2
                        WHEN turno = 'Tarde (12h-17h)' THEN 3
                        WHEN turno = 'Noite (18h-23h)' THEN 4
                    END,
                    tipo_erro
            """)
            
            dados = [
                {
                    'turno': row[0],
                    'Tipo de Erro': row[1],
                    'Contagem': row[2]
                }
                for row in cursor.fetchall()
            ]

            df = pd.DataFrame(dados)
            if df.empty:
                return JsonResponse({'error': 'Nenhum dado encontrado'}, status=404)
                
            total_por_turno = df.groupby('turno')['Contagem'].transform('sum')
            df['Proporcao'] = df['Contagem'] / total_por_turno
            df['Proporcao'] = df['Proporcao'].fillna(0)

            plot_data = [{
                'z': df.pivot_table(
                    values='Proporcao', 
                    index='turno',
                    columns='Tipo de Erro'
                ).values.tolist(),
                'x': sorted(df['Tipo de Erro'].unique()),
                'y': sorted(df['turno'].unique()),
                'type': 'heatmap',
                'colorscale': [
                    [0, '#e9f5f3'],
                    [1, '#298377']
                ],
                'text': df.pivot_table(
                    values='Proporcao',
                    index='turno',
                    columns='Tipo de Erro'
                ).applymap(lambda x: f'{x:.1%}').values.tolist(),
                'texttemplate': '%{text}',
                'textfont': {'size': 13, 'family': 'Arial', 'color': 'black'},
                'hovertemplate': '<b>Período:</b> %{y}<br><b>Tipo:</b> %{x}<br><b>Proporção:</b> %{text}<extra></extra>'
            }]

            layout = {
                'margin': {'l': 40, 'r': 40, 't': 40, 'b': 40},
                'title': {
                    'text': 'Análise de Erros por Turno',
                    'font': {'size': 16, 'family': 'Arial', 'color': '#298377'}
                },
                'xaxis': {
                    'title': 'Tipo de Erro',
                    'titlefont': {'size': 14, 'family': 'Arial'}
                },
                'yaxis': {
                    'title': 'Período do Dia',
                    'titlefont': {'size': 14, 'family': 'Arial'}
                },
                'paper_bgcolor': 'rgba(0,0,0,0)',
                'plot_bgcolor': 'rgba(0,0,0,0)'
            }

            return JsonResponse({'plot_data': plot_data, 'layout': layout})

    except Exception as e:
        print(f"Erro: {str(e)}")  # Para debug
        return JsonResponse({'error': str(e)}, status=500)

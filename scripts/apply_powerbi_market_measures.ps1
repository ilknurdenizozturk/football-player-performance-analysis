param(
    [Parameter(Mandatory = $false)]
    [int]$Port = 0
)

if ($Port -eq 0) {
    $proc = Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $proc) { throw "Power BI Desktop açık değil veya msmdsrv bulunamadı." }
    $portLine = netstat -ano | Select-String "LISTENING" | Select-String "\s$($proc.Id)$" | Select-Object -First 1
    if ($null -eq $portLine) { throw "msmdsrv portu tespit edilemedi (PID $($proc.Id))." }
    $Port = [int]($portLine.Line.Trim() -split '\s+')[1].Split(':')[-1]
    Write-Output "msmdsrv otomatik tespit edildi: PID $($proc.Id) → Port $Port"
}

$tum  = 'T' + [char]0x00FC + 'm'          # Tüm
$ulke = [char]0x00FC + 'lkeler'            # ülkeler
$Ulke = [char]0x00DC + 'lkeler'            # Ülkeler (capital)

$bin = 'C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_2.155.756.0_x64__8wekyb3d8bbwe\bin'
Add-Type -Path (Join-Path $bin 'Microsoft.AnalysisServices.Server.Core.dll')
Add-Type -Path (Join-Path $bin 'Microsoft.AnalysisServices.Server.Tabular.dll')

$measures = @(
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Transfer Count'
        Expression = 'DISTINCTCOUNT(fct_transfer_market_value_analysis[transfer_key])'
        Format = '#,0 "transfer"'
        Folder = 'Market Value Analysis\01 Scope'
        Description = 'Distinct transfer records in the active filter context.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Known Fee Transfer Count'
        Expression = 'CALCULATE([Transfer Count], fct_transfer_market_value_analysis[has_known_transfer_fee] = TRUE())'
        Format = '#,0 "transfer"'
        Folder = 'Market Value Analysis\01 Scope'
        Description = 'Transfers with a known transfer fee.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Known Fee Coverage %'
        Expression = 'COALESCE(DIVIDE([Known Fee Transfer Count], [Transfer Count]), 0)'
        Format = '0.0%'
        Folder = 'Market Value Analysis\02 Data Trust'
        Description = 'Share of transfer records with a known transfer fee.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Average Known Transfer Fee'
        Expression = 'CALCULATE(AVERAGE(fct_transfer_market_value_analysis[transfer_fee]), fct_transfer_market_value_analysis[has_known_transfer_fee] = TRUE())'
        Format = ([char]0x20AC + '0.0')
        Folder = 'Market Value Analysis\03 Commercial Value'
        Description = 'Average transfer fee, excluding unknown fee records.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Total Known Transfer Fee'
        Expression = 'CALCULATE(SUM(fct_transfer_market_value_analysis[transfer_fee]), fct_transfer_market_value_analysis[has_known_transfer_fee] = TRUE())'
        Format = ([char]0x20AC + '0.0')
        Folder = 'Market Value Analysis\03 Commercial Value'
        Description = 'Total known transfer fee in the active filter context.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Comparable Transfer Count'
        Expression = 'CALCULATE([Transfer Count], fct_transfer_market_value_analysis[has_fee_market_value_comparison] = TRUE())'
        Format = '#,0 "transfer"'
        Folder = 'Market Value Analysis\02 Data Trust'
        Description = 'Transfers with both a known fee and a market-value baseline.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Comparison Coverage %'
        Expression = 'DIVIDE([Comparable Transfer Count], [Transfer Count])'
        Format = '0.0%'
        Folder = 'Market Value Analysis\02 Data Trust'
        Description = 'Share of transfer records eligible for fee versus market-value comparison.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Average Fee Premium Discount %'
        Expression = 'DIVIDE(CALCULATE(AVERAGE(fct_transfer_market_value_analysis[fee_market_value_difference_pct]), fct_transfer_market_value_analysis[has_fee_market_value_comparison] = TRUE()), 100)'
        Format = '0.0%'
        Folder = 'Market Value Analysis\03 Commercial Value'
        Description = 'Average fee premium or discount versus the market-value baseline.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Post Transfer Outcome Count'
        Expression = 'CALCULATE([Transfer Count], fct_transfer_market_value_analysis[has_post_transfer_value_change] = TRUE())'
        Format = '#,0 "transfer"'
        Folder = 'Market Value Analysis\02 Data Trust'
        Description = 'Transfers with an observable post-transfer market-value outcome.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Post Transfer Outcome Coverage %'
        Expression = 'COALESCE(DIVIDE([Post Transfer Outcome Count], [Transfer Count]), 0)'
        Format = '0.0%'
        Folder = 'Market Value Analysis\02 Data Trust'
        Description = 'Share of transfers with an observable post-transfer value outcome.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Average Post Transfer Value Change %'
        Expression = 'DIVIDE(CALCULATE(AVERAGE(fct_transfer_market_value_analysis[market_value_change_after_transfer_pct]), fct_transfer_market_value_analysis[has_post_transfer_value_change] = TRUE()), 100)'
        Format = '0.0%'
        Folder = 'Market Value Analysis\04 Outcomes'
        Description = 'Average post-transfer market-value change for observable outcomes.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Value Increase Rate %'
        Expression = 'COALESCE(DIVIDE(CALCULATE([Transfer Count], fct_transfer_market_value_analysis[market_value_direction_after_transfer] = "increase"), [Post Transfer Outcome Count]), 0)'
        Format = '0.0%'
        Folder = 'Market Value Analysis\04 Outcomes'
        Description = 'Share of observable transfer outcomes with a market-value increase.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Selected Transfer Player'
        Expression = 'SELECTEDVALUE(fct_transfer_market_value_analysis[player_name], "Oyuncu secilmedi")'
        Format = ''
        Folder = 'Market Value Analysis\05 Dynamic Context'
        Description = 'Selected player label for drill-through pages.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Transfer Context Summary'
        Expression = 'VAR SeasonLabel = SELECTEDVALUE(fct_transfer_market_value_analysis[transfer_season], "' + $tum + ' sezonlar") VAR PositionLabel = SELECTEDVALUE(fct_transfer_market_value_analysis[position], "' + $tum + ' pozisyonlar") RETURN SeasonLabel & " | " & PositionLabel & " | " & FORMAT([Transfer Count], "#,0") & " transfer"'
        Format = ''
        Folder = 'Market Value Analysis\05 Dynamic Context'
        Description = 'Dynamic context summary driven by active filters.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Scored Player Count'
        Expression = 'DISTINCTCOUNT(ml_player_market_value_current_predictions[player_id])'
        Format = '#,0 "oyuncu"'
        Folder = 'Market Value Prediction\01 Scope'
        Description = 'Distinct players with a current market-value prediction.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Decision Ready Player Count'
        Expression = 'CALCULATE([Scored Player Count], ml_player_market_value_current_predictions[prediction_quality_status] IN {"high", "medium"})'
        Format = '#,0 "oyuncu"'
        Folder = 'Market Value Prediction\02 Trust'
        Description = 'Players with high or medium prediction quality.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Decision Ready Rate %'
        Expression = 'COALESCE(DIVIDE([Decision Ready Player Count], [Scored Player Count]), 0)'
        Format = '0.0%'
        Folder = 'Market Value Prediction\02 Trust'
        Description = 'Share of scored players suitable for decision support.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Average Predicted Market Value'
        Expression = 'AVERAGE(ml_player_market_value_current_predictions[predicted_market_value_eur])'
        Format = ([char]0x20AC + '0.0')
        Folder = 'Market Value Prediction\03 Valuation'
        Description = 'Average current predicted market value.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Average Previous Market Value'
        Expression = 'AVERAGE(ml_player_market_value_current_predictions[previous_market_value_eur])'
        Format = ([char]0x20AC + '0.0')
        Folder = 'Market Value Prediction\03 Valuation'
        Description = 'Average previous observed market value.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Average Prediction Upside %'
        Expression = 'DIVIDE(AVERAGE(ml_player_market_value_current_predictions[prediction_delta_vs_previous_pct]), 100)'
        Format = '0.0%'
        Folder = 'Market Value Prediction\04 Opportunity'
        Description = 'Average predicted percentage change versus previous market value.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Positive Upside Player Count'
        Expression = 'CALCULATE([Scored Player Count], ml_player_market_value_current_predictions[prediction_delta_vs_previous_pct] > 0)'
        Format = '#,0 "oyuncu"'
        Folder = 'Market Value Prediction\04 Opportunity'
        Description = 'Players with positive predicted upside versus previous market value.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Positive Upside Rate %'
        Expression = 'COALESCE(DIVIDE([Positive Upside Player Count], [Scored Player Count]), 0)'
        Format = '0.0%'
        Folder = 'Market Value Prediction\04 Opportunity'
        Description = 'Share of scored players with positive predicted upside.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Average Prediction Interval'
        Expression = 'AVERAGE(ml_player_market_value_current_predictions[prediction_interval_eur])'
        Format = ([char]0x20AC + '0.0')
        Folder = 'Market Value Prediction\02 Trust'
        Description = 'Average prediction interval width.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Average Relative Prediction Interval %'
        Expression = 'DIVIDE([Average Prediction Interval], [Average Predicted Market Value])'
        Format = '0.0%'
        Folder = 'Market Value Prediction\02 Trust'
        Description = 'Average prediction interval relative to predicted market value.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Selected Prediction Player'
        Expression = 'SELECTEDVALUE(ml_player_market_value_current_predictions[player_name], "Oyuncu secilmedi")'
        Format = ''
        Folder = 'Market Value Prediction\05 Dynamic Context'
        Description = 'Selected player label for drill-through pages.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Prediction Context Summary'
        Expression = 'VAR PositionLabel = SELECTEDVALUE(ml_player_market_value_current_predictions[position], "' + $tum + ' pozisyonlar") VAR CountryLabel = SELECTEDVALUE(ml_player_market_value_current_predictions[competition_country_name], "' + $tum + ' ' + $ulke + '") RETURN PositionLabel & " | " & CountryLabel & " | " & FORMAT([Scored Player Count], "#,0") & " oyuncu"'
        Format = ''
        Folder = 'Market Value Prediction\05 Dynamic Context'
        Description = 'Dynamic prediction context summary driven by active filters.'
    },
    @{
        Table = 'ml_player_market_value_quality_gates'
        Name = 'Quality Gates Passed'
        Expression = 'CALCULATE(COUNTROWS(ml_player_market_value_quality_gates), ml_player_market_value_quality_gates[passed] = TRUE())'
        Format = '#,0'
        Folder = 'ML Model Quality\01 Gates'
        Description = 'Number of quality gates that passed.'
    },
    @{
        Table = 'ml_player_market_value_quality_gates'
        Name = 'Quality Gates Total'
        Expression = 'COUNTROWS(ml_player_market_value_quality_gates)'
        Format = '#,0'
        Folder = 'ML Model Quality\01 Gates'
        Description = 'Total number of quality gates evaluated.'
    },

    # --- NEW measures added in session 2026-06-17 ---

    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Page 005 Dynamic Title'
        Expression = ('VAR s = SELECTEDVALUE(fct_transfer_market_value_analysis[transfer_season], "' + $tum + ' Sezonlar") ' +
                      'VAR p = SELECTEDVALUE(fct_transfer_market_value_analysis[pozisyon_tr], "' + $tum + ' Pozisyonlar") ' +
                      'RETURN "' + [char]::ConvertFromUtf32(0x1F4B0) +
                      ' Transfer & Piyasa De' + [char]0x011F + 'eri  ' + [char]0x2502 +
                      '  " & s & "  ' + [char]0x2502 + '  " & p')
        Format = ''
        Folder = 'Market Value Analysis\05 Dynamic Context'
        Description = 'Dynamic page title driven by active slicer selections.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'High Premium Transfer Count'
        Expression = 'CALCULATE([Transfer Count], fct_transfer_market_value_analysis[fee_market_value_difference_pct] > 30)'
        Format = '#,0 "transfer"'
        Folder = 'Market Value Analysis\03 Commercial Value'
        Description = 'Transfers where the fee exceeds market value by more than 30 percent — competitive bidding signal.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Transfer Value Index'
        Expression = 'DIVIDE(CALCULATE(SUM(fct_transfer_market_value_analysis[transfer_fee]), fct_transfer_market_value_analysis[has_known_transfer_fee] = TRUE()), CALCULATE(SUM(fct_transfer_market_value_analysis[market_value_baseline]), fct_transfer_market_value_analysis[has_market_value_baseline] = TRUE()))'
        Format = '0.00x'
        Folder = 'Market Value Analysis\03 Commercial Value'
        Description = 'Ratio of total known fees to total market value baselines — market efficiency index.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'YoY Avg Fee Change %'
        Expression = ('VAR CY = CALCULATE([Average Known Transfer Fee]) ' +
                      'VAR PY = CALCULATE([Average Known Transfer Fee], FILTER(ALL(fct_transfer_market_value_analysis[transfer_year]), fct_transfer_market_value_analysis[transfer_year] = MAX(fct_transfer_market_value_analysis[transfer_year]) - 1)) ' +
                      'RETURN DIVIDE(CY - PY, PY)')
        Format = '+0.0%;-0.0%;0.0%'
        Folder = 'Market Value Analysis\03 Commercial Value'
        Description = 'Year-over-year change in average known transfer fee.'
    },
    @{
        Table = 'fct_transfer_market_value_analysis'
        Name = 'Max Known Transfer Fee'
        Expression = 'CALCULATE(MAX(fct_transfer_market_value_analysis[transfer_fee]), fct_transfer_market_value_analysis[has_known_transfer_fee] = TRUE())'
        Format = ([char]0x20AC + '0.0')
        Folder = 'Market Value Analysis\03 Commercial Value'
        Description = 'Maximum known transfer fee in the active filter context.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'ML Page Dynamic Title'
        Expression = ('VAR p = SELECTEDVALUE(ml_player_market_value_current_predictions[pozisyon_tr], "' + $tum + ' Pozisyonlar") ' +
                      'VAR c = SELECTEDVALUE(ml_player_market_value_current_predictions[competition_country_name], "' + $tum + ' ' + $Ulke + '") ' +
                      'RETURN "' + [char]0x2B50 +
                      ' Piyasa De' + [char]0x011F + 'eri Tahmini  ' + [char]0x2502 +
                      '  " & p & "  ' + [char]0x2502 + '  " & c')
        Format = ''
        Folder = 'Market Value Prediction\05 Dynamic Context'
        Description = 'Dynamic page title driven by active slicer selections.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = ('B' + [char]0x00FC + 'y' + [char]0x00FC + 'k Art' + [char]0x0131 + [char]0x015F + ' Oyuncu Count')
        Expression = 'CALCULATE([Scored Player Count], ml_player_market_value_current_predictions[prediction_delta_vs_previous_pct] > 20)'
        Format = '#,0 "oyuncu"'
        Folder = 'Market Value Prediction\04 Opportunity'
        Description = 'Players with predicted upside greater than 20 percent — high-opportunity targets.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'Average Prediction Confidence %'
        Expression = '1 - [Average Relative Prediction Interval %]'
        Format = '0.0%'
        Folder = 'Market Value Prediction\02 Trust'
        Description = 'Inverse of average relative interval — higher means more confident predictions.'
    },
    @{
        Table = 'ml_player_market_value_current_predictions'
        Name = 'High Upside Decision Ready Count'
        Expression = 'CALCULATE([Decision Ready Player Count], ml_player_market_value_current_predictions[prediction_delta_vs_previous_pct] > 0)'
        Format = '#,0 "oyuncu"'
        Folder = 'Market Value Prediction\04 Opportunity'
        Description = 'Decision-ready players with positive predicted upside — actionable long list.'
    }
)

$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect("localhost:$Port")

try {
    $database = $server.Databases[0]
    $model = $database.Model

    foreach ($definition in $measures) {
        $table = $model.Tables.Find($definition.Table)
        if ($null -eq $table) {
            throw "Table not found: $($definition.Table)"
        }

        $measure = $table.Measures.Find($definition.Name)
        if ($null -eq $measure) {
            $measure = New-Object Microsoft.AnalysisServices.Tabular.Measure
            $measure.Name = $definition.Name
            $table.Measures.Add($measure)
        }

        $measure.Expression = $definition.Expression
        $measure.FormatString = $definition.Format
        $measure.DisplayFolder = $definition.Folder
        $measure.Description = $definition.Description
    }

    # --- Cleanup: remove any wrongly-typed calculated columns (should be measures) ---

    $wrongCalcCols = @(
        @{ Table = 'fct_transfer_cohort_performance'; Names = @('Observed Transfer Outcomes','Transfer Outcome Coverage %','Average Reliable Cohort Median Value Change %') },
        @{ Table = 'fct_transfer_fixed_horizon_outcomes'; Names = @('Historical Transfers','Observed 365d Transfers','365d Outcome Coverage %','Median 365d Value Change %') },
        @{ Table = 'fct_data_coverage_bias'; Names = @('Known Fee Coverage % (Bias)') },
        @{ Table = 'fct_club_transfer_portfolio'; Names = @('Net Transfer Spend') },
        @{ Table = 'fct_club_risk_profile'; Names = @('Reliable Club Transfer Success Rate %') },
        @{ Table = 'fct_player_rolling_form'; Names = @('Rolling 5 Goals per 90') }
    )
    foreach ($entry in $wrongCalcCols) {
        $tbl = $model.Tables.Find($entry.Table)
        if ($null -eq $tbl) { continue }
        foreach ($colName in $entry.Names) {
            $col = $tbl.Columns | Where-Object { $_.Name -eq $colName -and $_ -is [Microsoft.AnalysisServices.Tabular.CalculatedColumn] }
            if ($null -ne $col) {
                $tbl.Columns.Remove($col) | Out-Null
                Write-Output "Removed wrong calc col: $($entry.Table)[$colName]"
            }
        }
    }

    # --- Additional measures from MEASURES.dax for remaining mart tables ---

    $additionalMeasures = @(
        @{
            Table = 'fct_transfer_cohort_performance'
            Name = 'Observed Transfer Outcomes'
            Expression = 'SUM(fct_transfer_cohort_performance[observed_outcome_count])'
            Format = '#,0'
            Folder = 'Cohort Analysis\01 Scope'
            Description = 'Total observed transfer outcomes across cohorts.'
        },
        @{
            Table = 'fct_transfer_cohort_performance'
            Name = 'Transfer Outcome Coverage %'
            Expression = 'DIVIDE(SUM(fct_transfer_cohort_performance[observed_outcome_count]), SUM(fct_transfer_cohort_performance[transfer_count]))'
            Format = '0.0%'
            Folder = 'Cohort Analysis\02 Data Trust'
            Description = 'Share of cohort transfers with an observable outcome.'
        },
        @{
            Table = 'fct_transfer_cohort_performance'
            Name = 'Average Reliable Cohort Median Value Change %'
            Expression = 'CALCULATE(AVERAGE(fct_transfer_cohort_performance[median_market_value_change_pct]), fct_transfer_cohort_performance[meets_minimum_sample_size] = TRUE())'
            Format = '0.0%'
            Folder = 'Cohort Analysis\03 Outcomes'
            Description = 'Average median market value change for cohorts meeting minimum sample size.'
        },
        @{
            Table = 'fct_transfer_fixed_horizon_outcomes'
            Name = 'Historical Transfers'
            Expression = 'DISTINCTCOUNT(fct_transfer_fixed_horizon_outcomes[transfer_key])'
            Format = '#,0'
            Folder = 'Fixed Horizon\01 Scope'
            Description = 'Distinct historical transfer records.'
        },
        @{
            Table = 'fct_transfer_fixed_horizon_outcomes'
            Name = 'Observed 365d Transfers'
            Expression = 'CALCULATE([Historical Transfers], fct_transfer_fixed_horizon_outcomes[has_365d_outcome] = TRUE())'
            Format = '#,0'
            Folder = 'Fixed Horizon\01 Scope'
            Description = 'Transfers with a 365-day post-transfer outcome.'
        },
        @{
            Table = 'fct_transfer_fixed_horizon_outcomes'
            Name = '365d Outcome Coverage %'
            Expression = 'DIVIDE([Observed 365d Transfers], [Historical Transfers])'
            Format = '0.0%'
            Folder = 'Fixed Horizon\02 Data Trust'
            Description = 'Share of historical transfers with a 365-day outcome.'
        },
        @{
            Table = 'fct_transfer_fixed_horizon_outcomes'
            Name = 'Median 365d Value Change %'
            Expression = 'CALCULATE(MEDIAN(fct_transfer_fixed_horizon_outcomes[market_value_change_365d_pct]), fct_transfer_fixed_horizon_outcomes[has_365d_outcome] = TRUE())'
            Format = '0.0%'
            Folder = 'Fixed Horizon\03 Outcomes'
            Description = 'Median 365-day market value change for observable outcomes.'
        },
        @{
            Table = 'fct_data_coverage_bias'
            Name = 'Known Fee Coverage % (Bias)'
            Expression = 'DIVIDE(SUM(fct_data_coverage_bias[known_fee_count]), SUM(fct_data_coverage_bias[transfer_count]))'
            Format = '0.0%'
            Folder = 'Coverage\01 Data Trust'
            Description = 'Known fee coverage rate from bias diagnostic table.'
        },
        @{
            Table = 'fct_club_transfer_portfolio'
            Name = 'Net Transfer Spend'
            Expression = 'SUM(fct_club_transfer_portfolio[net_transfer_spend])'
            Format = ([char]0x20AC + '0.0')
            Folder = 'Club Portfolio\01 Commercial'
            Description = 'Net club transfer spend (buy minus sell) in EUR.'
        },
        @{
            Table = 'fct_club_risk_profile'
            Name = 'Reliable Club Transfer Success Rate %'
            Expression = 'CALCULATE(AVERAGE(fct_club_risk_profile[transfer_success_rate_pct]), fct_club_risk_profile[meets_minimum_sample_size] = TRUE())'
            Format = '0.0%'
            Folder = 'Club Risk\01 Outcomes'
            Description = 'Average transfer success rate for clubs meeting minimum sample size.'
        },
        @{
            Table = 'fct_player_rolling_form'
            Name = 'Rolling 5 Goals per 90'
            Expression = 'AVERAGE(fct_player_rolling_form[rolling_5_goals_per_90])'
            Format = '0.00'
            Folder = 'Rolling Form\01 Performance'
            Description = 'Average rolling 5-appearance goals per 90 minutes.'
        }
    )

    foreach ($definition in $additionalMeasures) {
        $table = $model.Tables.Find($definition.Table)
        if ($null -eq $table) {
            Write-Warning "Table not found: $($definition.Table) - skipping"
            continue
        }
        $measure = $table.Measures.Find($definition.Name)
        if ($null -eq $measure) {
            $measure = New-Object Microsoft.AnalysisServices.Tabular.Measure
            $measure.Name = $definition.Name
            $table.Measures.Add($measure)
        }
        $measure.Expression = $definition.Expression
        $measure.FormatString = $definition.Format
        $measure.DisplayFolder = $definition.Folder
        $measure.Description = $definition.Description
    }

    # --- Remaining mart tables: full DAX coverage ---

    $remainingMartMeasures = @(

        # fct_player_performance
        @{ Table='fct_player_performance'; Name='Player Performance Count'; Expression='DISTINCTCOUNT(fct_player_performance[player_id])'; Format='#,0 "oyuncu"'; Folder='Player Performance\01 Scope'; Description='Distinct players with performance records.' },
        @{ Table='fct_player_performance'; Name='Players with Market Value'; Expression='CALCULATE(DISTINCTCOUNT(fct_player_performance[player_id]), fct_player_performance[has_current_market_value] = TRUE())'; Format='#,0 "oyuncu"'; Folder='Player Performance\02 Market Value'; Description='Players with a current market value on record.' },
        @{ Table='fct_player_performance'; Name='Average Current Market Value'; Expression='CALCULATE(AVERAGE(fct_player_performance[market_value_in_eur]), fct_player_performance[has_current_market_value] = TRUE())'; Format=([char]0x20AC+'0.0'); Folder='Player Performance\02 Market Value'; Description='Average current market value among players with a valuation.' },
        @{ Table='fct_player_performance'; Name='Average Goals per 90'; Expression='AVERAGE(fct_player_performance[goals_per_90])'; Format='0.00'; Folder='Player Performance\03 Output'; Description='Average goals scored per 90 minutes played.' },
        @{ Table='fct_player_performance'; Name='Average Assists per 90'; Expression='AVERAGE(fct_player_performance[assists_per_90])'; Format='0.00'; Folder='Player Performance\03 Output'; Description='Average assists per 90 minutes played.' },
        @{ Table='fct_player_performance'; Name='Total Performance Goals'; Expression='SUM(fct_player_performance[total_goals])'; Format='#,0'; Folder='Player Performance\03 Output'; Description='Total goals across all player records in filter.' },
        @{ Table='fct_player_performance'; Name='Total Performance Assists'; Expression='SUM(fct_player_performance[total_assists])'; Format='#,0'; Folder='Player Performance\03 Output'; Description='Total assists across all player records in filter.' },

        # fct_market_value_history
        @{ Table='fct_market_value_history'; Name='Market Value Records'; Expression='COUNTROWS(fct_market_value_history)'; Format='#,0'; Folder='Market Value History\01 Scope'; Description='Total market value valuation records.' },
        @{ Table='fct_market_value_history'; Name='Players Tracked'; Expression='DISTINCTCOUNT(fct_market_value_history[player_id])'; Format='#,0 "oyuncu"'; Folder='Market Value History\01 Scope'; Description='Distinct players with at least one market value record.' },
        @{ Table='fct_market_value_history'; Name='Average Historical Market Value'; Expression='CALCULATE(AVERAGE(fct_market_value_history[market_value_in_eur]), NOT ISBLANK(fct_market_value_history[market_value_in_eur]))'; Format=([char]0x20AC+'0.0'); Folder='Market Value History\02 Valuation'; Description='Average market value across all historical valuations.' },
        @{ Table='fct_market_value_history'; Name='Peak Historical Market Value'; Expression='MAX(fct_market_value_history[market_value_in_eur])'; Format=([char]0x20AC+'0.0'); Folder='Market Value History\02 Valuation'; Description='Highest recorded market value in the active filter context.' },

        # fct_club_performance
        @{ Table='fct_club_performance'; Name='Club Count'; Expression='DISTINCTCOUNT(fct_club_performance[club_id])'; Format='#,0 "kulup"'; Folder='Club Performance\01 Scope'; Description='Distinct clubs with aggregate performance records.' },
        @{ Table='fct_club_performance'; Name='Club Win Rate %'; Expression='DIVIDE(SUM(fct_club_performance[wins]), SUM(fct_club_performance[matches_played]))'; Format='0.0%'; Folder='Club Performance\02 Results'; Description='Aggregate win rate across filtered clubs.' },
        @{ Table='fct_club_performance'; Name='Club Goals per Game'; Expression='DIVIDE(SUM(fct_club_performance[goals_scored]), SUM(fct_club_performance[matches_played]))'; Format='0.00'; Folder='Club Performance\02 Results'; Description='Goals scored per match across filtered clubs.' },
        @{ Table='fct_club_performance'; Name='Club Goals Conceded per Game'; Expression='DIVIDE(SUM(fct_club_performance[goals_conceded]), SUM(fct_club_performance[matches_played]))'; Format='0.00'; Folder='Club Performance\02 Results'; Description='Goals conceded per match across filtered clubs.' },

        # fct_club_season_performance
        @{ Table='fct_club_season_performance'; Name='Club Seasons'; Expression='COUNTROWS(fct_club_season_performance)'; Format='#,0'; Folder='Club Season\01 Scope'; Description='Club-season combinations in current filter.' },
        @{ Table='fct_club_season_performance'; Name='Season Win Rate %'; Expression='DIVIDE(SUM(fct_club_season_performance[wins]), SUM(fct_club_season_performance[matches_played]))'; Format='0.0%'; Folder='Club Season\02 Results'; Description='Aggregate win rate across filtered club-seasons.' },
        @{ Table='fct_club_season_performance'; Name='Season Goals per Game'; Expression='DIVIDE(SUM(fct_club_season_performance[goals_scored]), SUM(fct_club_season_performance[matches_played]))'; Format='0.00'; Folder='Club Season\02 Results'; Description='Goals scored per match across filtered club-seasons.' },
        @{ Table='fct_club_season_performance'; Name='Average Season Attendance'; Expression='CALCULATE(AVERAGE(fct_club_season_performance[avg_attendance]), NOT ISBLANK(fct_club_season_performance[avg_attendance]))'; Format='#,0'; Folder='Club Season\03 Commercial'; Description='Average match attendance across filtered club-seasons.' },

        # fct_transfer_success_labels
        @{ Table='fct_transfer_success_labels'; Name='Labeled Transfer Count'; Expression='DISTINCTCOUNT(fct_transfer_success_labels[transfer_key])'; Format='#,0 "transfer"'; Folder='Transfer Labels\01 Scope'; Description='Distinct transfer records with ML success labels.' },
        @{ Table='fct_transfer_success_labels'; Name='Successful Transfer Count'; Expression='CALCULATE(DISTINCTCOUNT(fct_transfer_success_labels[transfer_key]), fct_transfer_success_labels[is_successful_transfer] = 1)'; Format='#,0 "transfer"'; Folder='Transfer Labels\02 Outcomes'; Description='Transfers classified as successful: >=20% value increase in 365 days.' },
        @{ Table='fct_transfer_success_labels'; Name='Transfer Success Rate %'; Expression='DIVIDE([Successful Transfer Count], [Labeled Transfer Count])'; Format='0.0%'; Folder='Transfer Labels\02 Outcomes'; Description='Share of labeled transfers classified as successful.' },
        @{ Table='fct_transfer_success_labels'; Name='Average Market Value Change at Horizon %'; Expression='CALCULATE(DIVIDE(AVERAGE(fct_transfer_success_labels[market_value_change_at_horizon_pct]), 100), fct_transfer_success_labels[label_status] = "complete")'; Format='0.0%'; Folder='Transfer Labels\02 Outcomes'; Description='Average 365-day market value change for complete outcome records.' },
        @{ Table='fct_transfer_success_labels'; Name='Average Age at Transfer'; Expression='AVERAGE(fct_transfer_success_labels[age_at_transfer])'; Format='0.0'; Folder='Transfer Labels\03 Demographics'; Description='Average player age at time of transfer.' },

        # fct_player_career_timeline
        @{ Table='fct_player_career_timeline'; Name='Career Records'; Expression='COUNTROWS(fct_player_career_timeline)'; Format='#,0'; Folder='Career Timeline\01 Scope'; Description='Player-season records in career timeline.' },
        @{ Table='fct_player_career_timeline'; Name='Players in Timeline'; Expression='DISTINCTCOUNT(fct_player_career_timeline[player_id])'; Format='#,0 "oyuncu"'; Folder='Career Timeline\01 Scope'; Description='Distinct players with career timeline records.' },
        @{ Table='fct_player_career_timeline'; Name='Average Season Market Value'; Expression='CALCULATE(AVERAGE(fct_player_career_timeline[season_market_value]), fct_player_career_timeline[has_season_market_value] = TRUE())'; Format=([char]0x20AC+'0.0'); Folder='Career Timeline\02 Valuation'; Description='Average season market value for seasons with valuation data.' },
        @{ Table='fct_player_career_timeline'; Name='Career Total Goals'; Expression='SUM(fct_player_career_timeline[total_goals])'; Format='#,0'; Folder='Career Timeline\03 Output'; Description='Total career goals across player-season records in filter.' },

        # fct_agent_portfolio
        @{ Table='fct_agent_portfolio'; Name='Agent Count'; Expression='COUNTROWS(fct_agent_portfolio)'; Format='#,0 "ajan"'; Folder='Agent Portfolio\01 Scope'; Description='Distinct agents in the portfolio table.' },
        @{ Table='fct_agent_portfolio'; Name='Total Managed Players'; Expression='SUM(fct_agent_portfolio[player_count])'; Format='#,0 "oyuncu"'; Folder='Agent Portfolio\01 Scope'; Description='Total players managed across all agents in filter.' },
        @{ Table='fct_agent_portfolio'; Name='Total Portfolio Market Value'; Expression='SUM(fct_agent_portfolio[total_current_market_value])'; Format=([char]0x20AC+'0.0'); Folder='Agent Portfolio\02 Valuation'; Description='Combined current market value of all managed players.' },
        @{ Table='fct_agent_portfolio'; Name='Average Portfolio Market Value'; Expression='AVERAGE(fct_agent_portfolio[avg_current_market_value])'; Format=([char]0x20AC+'0.0'); Folder='Agent Portfolio\02 Valuation'; Description='Average current market value per agent across managed players.' },
        @{ Table='fct_agent_portfolio'; Name='Total Agent Known Transfer Fee'; Expression='SUM(fct_agent_portfolio[total_known_transfer_fee])'; Format=([char]0x20AC+'0.0'); Folder='Agent Portfolio\03 Commercial'; Description='Total known transfer fee volume brokered by agents in filter.' },

        # fct_competition_performance
        @{ Table='fct_competition_performance'; Name='Competition Count'; Expression='DISTINCTCOUNT(fct_competition_performance[competition_id])'; Format='#,0 "lig"'; Folder='Competition\01 Scope'; Description='Distinct competitions in current filter.' },
        @{ Table='fct_competition_performance'; Name='Total Competition Matches'; Expression='SUM(fct_competition_performance[matches_played])'; Format='#,0'; Folder='Competition\01 Scope'; Description='Total matches played across competitions in filter.' },
        @{ Table='fct_competition_performance'; Name='Average Competition Goals per Match'; Expression='CALCULATE(AVERAGE(fct_competition_performance[avg_goals_per_match]), NOT ISBLANK(fct_competition_performance[avg_goals_per_match]))'; Format='0.00'; Folder='Competition\02 Outcomes'; Description='Average goals per match across competitions in filter.' },
        @{ Table='fct_competition_performance'; Name='Average Competition Attendance'; Expression='CALCULATE(AVERAGE(fct_competition_performance[avg_attendance]), NOT ISBLANK(fct_competition_performance[avg_attendance]))'; Format='#,0'; Folder='Competition\03 Commercial'; Description='Average match attendance across competitions in filter.' },
        @{ Table='fct_competition_performance'; Name='Average Clubs per Competition'; Expression='AVERAGE(fct_competition_performance[club_participation_count])'; Format='0.0'; Folder='Competition\01 Scope'; Description='Average number of clubs participating per competition.' },

        # fct_transfers (raw)
        @{ Table='fct_transfers'; Name='Raw Transfer Count'; Expression='COUNTROWS(fct_transfers)'; Format='#,0 "transfer"'; Folder='Transfers\01 Scope'; Description='Total raw transfer records across all seasons and types.' },
        @{ Table='fct_transfers'; Name='Known Fee Raw Count'; Expression='CALCULATE(COUNTROWS(fct_transfers), NOT ISBLANK(fct_transfers[transfer_fee]))'; Format='#,0 "transfer"'; Folder='Transfers\01 Scope'; Description='Raw transfer records with a known transfer fee.' },
        @{ Table='fct_transfers'; Name='Total Known Fee Volume'; Expression='SUM(fct_transfers[transfer_fee])'; Format=([char]0x20AC+'0.0'); Folder='Transfers\02 Commercial'; Description='Total known transfer fee volume across all raw transfers.' },
        @{ Table='fct_transfers'; Name='Average Market Value at Transfer'; Expression='CALCULATE(AVERAGE(fct_transfers[market_value_in_eur]), NOT ISBLANK(fct_transfers[market_value_in_eur]))'; Format=([char]0x20AC+'0.0'); Folder='Transfers\03 Valuation'; Description='Average player market value at time of raw transfer.' },

        # fct_match
        @{ Table='fct_match'; Name='Match Count'; Expression='DISTINCTCOUNT(fct_match[game_id])'; Format='#,0 "mac"'; Folder='Match\01 Scope'; Description='Distinct matches in the active filter context.' },
        @{ Table='fct_match'; Name='Total Match Goals'; Expression='SUM(fct_match[total_goals])'; Format='#,0'; Folder='Match\02 Results'; Description='Total goals scored across all matches in filter.' },
        @{ Table='fct_match'; Name='Average Match Goals'; Expression='DIVIDE(SUM(fct_match[total_goals]), DISTINCTCOUNT(fct_match[game_id]))'; Format='0.00'; Folder='Match\02 Results'; Description='Average total goals per match.' },
        @{ Table='fct_match'; Name='Average Attendance'; Expression='CALCULATE(AVERAGE(fct_match[attendance]), fct_match[has_attendance] = TRUE())'; Format='#,0'; Folder='Match\03 Commercial'; Description='Average match attendance where reported.' },
        @{ Table='fct_match'; Name='Home Win Rate %'; Expression='DIVIDE(CALCULATE(DISTINCTCOUNT(fct_match[game_id]), fct_match[match_result] = "home_win"), CALCULATE(DISTINCTCOUNT(fct_match[game_id]), fct_match[match_result] <> "draw"))'; Format='0.0%'; Folder='Match\02 Results'; Description='Home team win rate across decisive matches (draws excluded).' },

        # fct_player_match_performance
        @{ Table='fct_player_match_performance'; Name='Appearance Count'; Expression='COUNTROWS(fct_player_match_performance)'; Format='#,0'; Folder='Match Performance\01 Scope'; Description='Total player match appearances in current filter.' },
        @{ Table='fct_player_match_performance'; Name='Distinct Players Appeared'; Expression='DISTINCTCOUNT(fct_player_match_performance[player_id])'; Format='#,0 "oyuncu"'; Folder='Match Performance\01 Scope'; Description='Distinct players with at least one appearance in filter.' },
        @{ Table='fct_player_match_performance'; Name='Distinct Matches'; Expression='DISTINCTCOUNT(fct_player_match_performance[game_id])'; Format='#,0 "mac"'; Folder='Match Performance\01 Scope'; Description='Distinct matches with tracked player performance.' },
        @{ Table='fct_player_match_performance'; Name='Home Appearance Rate %'; Expression='DIVIDE(CALCULATE(COUNTROWS(fct_player_match_performance), fct_player_match_performance[hosting] = "home"), COUNTROWS(fct_player_match_performance))'; Format='0.0%'; Folder='Match Performance\02 Context'; Description='Share of player appearances in home matches.' }
    )

    foreach ($definition in $remainingMartMeasures) {
        $table = $model.Tables.Find($definition.Table)
        if ($null -eq $table) {
            Write-Warning "Table not found: $($definition.Table) - skipping"
            continue
        }
        $measure = $table.Measures.Find($definition.Name)
        if ($null -eq $measure) {
            $measure = New-Object Microsoft.AnalysisServices.Tabular.Measure
            $measure.Name = $definition.Name
            $table.Measures.Add($measure)
        }
        $measure.Expression = $definition.Expression
        $measure.FormatString = $definition.Format
        $measure.DisplayFolder = $definition.Folder
        $measure.Description = $definition.Description
    }

    # --- Calculated columns for Turkish display labels ---

    $calcColumns = @(
        @{
            Table = 'fct_transfer_market_value_analysis'
            Name = 'Yon Etiketi TR'
            Expression = 'SWITCH(fct_transfer_market_value_analysis[market_value_direction_after_transfer], "increase", "Arttı", "decrease", "Düştü", "unchanged", "Değişmedi", "unavailable", "Belirsiz", fct_transfer_market_value_analysis[market_value_direction_after_transfer])'
        },
        @{
            Table = 'fct_transfer_market_value_analysis'
            Name = 'Pozisyon TR'
            Expression = 'SWITCH(fct_transfer_market_value_analysis[position], "Attack", "Forvet", "Defender", "Defans", "Goalkeeper", "Kaleci", "Midfield", "Orta Saha", "Missing", "Bilinmiyor", fct_transfer_market_value_analysis[position])'
        },
        @{
            Table = 'ml_player_market_value_current_predictions'
            Name = 'Kalite Etiketi TR'
            Expression = 'SWITCH(ml_player_market_value_current_predictions[prediction_quality_status], "high", "Yüksek", "medium", "Orta", "limited", "Sınırlı", ml_player_market_value_current_predictions[prediction_quality_status])'
        },
        @{
            Table = 'ml_player_market_value_current_predictions'
            Name = 'Pozisyon TR'
            Expression = 'SWITCH(ml_player_market_value_current_predictions[position], "Attack", "Forvet", "Defender", "Defans", "Goalkeeper", "Kaleci", "Midfield", "Orta Saha", "Missing", "Bilinmiyor", ml_player_market_value_current_predictions[position])'
        },
        @{
            Table = 'fct_transfer_market_value_analysis'
            Name = 'fee_range_category_tr'
            Expression = ('SWITCH(TRUE(), ' +
                          '[transfer_fee] >= 50000000, "Mega Transfer (' + [char]0x2265 + '50M' + [char]0x20AC + ')", ' +
                          '[transfer_fee] >= 20000000, "B' + [char]0x00FC + 'y' + [char]0x00FC + 'k Transfer (20-50M' + [char]0x20AC + ')", ' +
                          '[transfer_fee] >= 5000000, "Orta Transfer (5-20M' + [char]0x20AC + ')", ' +
                          '[transfer_fee] > 0, "K' + [char]0x00FC + [char]0x00E7 + [char]0x00FC + 'k Transfer (<5M' + [char]0x20AC + ')", ' +
                          'NOT([has_known_transfer_fee]), "' + [char]0x00DC + 'cretsiz/Bilinmiyor", ' +
                          '"Veri Yok")')
        }
    )

    $affectedCalcColTables = @{}
    foreach ($definition in $calcColumns) {
        $table = $model.Tables.Find($definition.Table)
        if ($null -eq $table) {
            Write-Warning "Table not found for calculated column: $($definition.Table) - skipping"
            continue
        }
        $existing = $table.Columns | Where-Object { $_.Name -eq $definition.Name }
        if ($null -eq $existing) {
            $col = New-Object Microsoft.AnalysisServices.Tabular.CalculatedColumn
            $col.Name = $definition.Name
            $col.Expression = $definition.Expression
            $table.Columns.Add($col) | Out-Null
            Write-Output "Added calculated column: $($definition.Table)[$($definition.Name)]"
        } else {
            $existing.Expression = $definition.Expression
            Write-Output "Updated calculated column: $($definition.Table)[$($definition.Name)]"
        }
        $affectedCalcColTables[$definition.Table] = $table
    }

    foreach ($tblEntry in $affectedCalcColTables.GetEnumerator()) {
        $tblEntry.Value.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Calculate) | Out-Null
        Write-Output "Recalculate requested: $($tblEntry.Key)"
    }

    # --- Fix BigQuery Storage API error 131 (UseStorageApi=false) ---
    $bigqueryFixed = 0
    foreach ($table in $model.Tables) {
        foreach ($partition in $table.Partitions) {
            $src = $partition.Source
            if ($null -ne $src -and $src.GetType().Name -eq 'MPartitionSource') {
                $expr = $src.Expression
                if ($null -ne $expr -and $expr -match 'GoogleBigQuery\.Database\(\s*\)') {
                    $src.Expression = $expr -replace 'GoogleBigQuery\.Database\(\s*\)', 'GoogleBigQuery.Database([UseStorageApi=false])'
                    $bigqueryFixed++
                    Write-Output "Fixed BigQuery connection: $($table.Name)"
                }
            }
        }
    }
    if ($bigqueryFixed -gt 0) {
        Write-Output "Total BigQuery connections fixed: $bigqueryFixed"
    } else {
        Write-Output "BigQuery: zaten düzeltilmiş veya partition bulunamadı."
    }

    $model.SaveChanges()

    $verifyTables = @(
        'fct_transfer_market_value_analysis',
        'ml_player_market_value_current_predictions',
        'ml_player_market_value_quality_gates',
        'fct_transfer_cohort_performance',
        'fct_transfer_fixed_horizon_outcomes',
        'fct_club_transfer_portfolio',
        'fct_club_risk_profile',
        'fct_player_rolling_form'
    )
    foreach ($tableName in $verifyTables) {
        $table = $model.Tables.Find($tableName)
        if ($null -ne $table) {
            $calcCols = ($table.Columns | Where-Object { $_ -is [Microsoft.AnalysisServices.Tabular.CalculatedColumn] }).Count
            Write-Output "$tableName - measures: $($table.Measures.Count), calc columns: $calcCols"
        }
    }
}
finally {
    $server.Disconnect()
}

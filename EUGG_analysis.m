% =========================================================================
% EUGG_analysis.m  |  Extended Theil decomposition analysis
% Run AFTER EUGG_model.m (requires EUGG_Results.xlsx + EUGG_Workspace.mat)
%
% Outputs (new Excel sheets appended to EUGG_Results.xlsx):
%   10_Between_Contrib   - Per-country T_between contribution: s_c * ln(s_c/p_c)
%   10b_Between_Ranked   - Same, sorted by BC_Change descending
%   11_IncGroup_Theil    - Income group x Theil decomposition
%   12_Region_Theil      - Region x Theil decomposition
%   13_TripleAsymm_4D    - 4D asymmetry: GDP/CO2/Gini/Within-T
%   14_Lorenz            - Lorenz curve data for Python figures
% =========================================================================
clear; clc;

script_dir = fileparts(mfilename('fullpath'));
if isempty(script_dir)
    script_dir = pwd;
end
dataDir    = fullfile(script_dir, 'results', 'Data');
fname_xlsx = fullfile(dataDir, 'EUGG_Results.xlsx');
fname_mat  = fullfile(dataDir, 'EUGG_Workspace.mat');

fprintf('[LOAD] Reading EUGG_Results.xlsx...\n');
T9 = readtable(fname_xlsx, 'Sheet', '9_Theil_Countries',  'VariableNamingRule', 'preserve');
T8 = readtable(fname_xlsx, 'Sheet', '8_Theil_Global',     'VariableNamingRule', 'preserve');
T4 = readtable(fname_xlsx, 'Sheet', '4_TripleAsymmetry',  'VariableNamingRule', 'preserve');
T1 = readtable(fname_xlsx, 'Sheet', '1_Global',           'VariableNamingRule', 'preserve');
fprintf('   Loaded: %d countries, %d Theil metrics.\n\n', height(T9), height(T8));

nC  = height(T9);
EPS = 1e-30;

% Pull T_between reference values for verification
T_between_base  = T8.Baseline(strcmp(T8.Metric, 'Theil_T_Between'));
T_between_final = T8.PostInvestment(strcmp(T8.Metric, 'Theil_T_Between'));
T_within_base   = T8.Baseline(strcmp(T8.Metric, 'Theil_T_Within'));
T_within_final  = T8.PostInvestment(strcmp(T8.Metric, 'Theil_T_Within'));
T_total_base    = T8.Baseline(strcmp(T8.Metric, 'Theil_T_Total'));
T_total_final   = T8.PostInvestment(strcmp(T8.Metric, 'Theil_T_Total'));

%% B: Per-country contribution to T_between
% BC_c = s_c * ln(s_c / p_c)
fprintf('[B] Computing per-country T_between contributions...\n');

s_b = T9.IncShare_Base;
s_f = T9.IncShare_Final;
p   = T9.PopShare;

valid_b = p > 1e-15 & s_b > 1e-15;
valid_f = p > 1e-15 & s_f > 1e-15;

BC_Base  = zeros(nC, 1);
BC_Final = zeros(nC, 1);
BC_Base(valid_b)  = s_b(valid_b) .* log(s_b(valid_b) ./ p(valid_b));
BC_Final(valid_f) = s_f(valid_f) .* log(s_f(valid_f) ./ p(valid_f));
BC_Change = BC_Final - BC_Base;

% Verify decomposition integrity
err_b = abs(sum(BC_Base)  - T_between_base);
err_f = abs(sum(BC_Final) - T_between_final);
fprintf('   Sum(BC_Base)  = %.6f  (ref: %.6f,  error = %.2e)\n', sum(BC_Base),  T_between_base,  err_b);
fprintf('   Sum(BC_Final) = %.6f  (ref: %.6f,  error = %.2e)\n', sum(BC_Final), T_between_final, err_f);
if max(err_b, err_f) > 1e-8
    warning('[B] BC sum deviates from T_between by >1e-8. Check data.');
end

% Export sheet 10
T_BC = T9(:, {'ID','Country','ISO3','Region','IncomeGroup','Investment_MEur','PopShare','IncShare_Base','IncShare_Final'});
T_BC.BC_Base      = BC_Base;
T_BC.BC_Final     = BC_Final;
T_BC.BC_Change    = BC_Change;
T_BC.BC_Pct_Base  = BC_Base  / (sum(BC_Base(valid_b))  + EPS) * 100;
T_BC.BC_Pct_Final = BC_Final / (sum(BC_Final(valid_f)) + EPS) * 100;
T_BC.BC_Pct_Change = T_BC.BC_Pct_Final - T_BC.BC_Pct_Base;
writetable(T_BC, fname_xlsx, 'Sheet', '10_Between_Contrib');

% Export sheet 10b (ranked by change)
[~, rank_idx] = sort(BC_Change, 'descend');
writetable(T_BC(rank_idx, :), fname_xlsx, 'Sheet', '10b_Between_Ranked');

fprintf('   Exported: 10_Between_Contrib, 10b_Between_Ranked\n\n');

%% C: Income group x Theil decomposition
fprintf('[C] Income group x Theil analysis...\n');

inc_labels = {'High income', 'Upper middle income', 'Lower middle income', 'Low income'};
nIG = length(inc_labels);
ig_group = cell(nC, 1);

ig_str = lower(string(T9.IncomeGroup));
for c = 1:nC
    s = ig_str(c);
    if     contains(s,'high') && ~contains(s,'upper'),      ig_group{c} = inc_labels{1};
    elseif contains(s,'upper'),                              ig_group{c} = inc_labels{2};
    elseif contains(s,'lower'),                              ig_group{c} = inc_labels{3};
    elseif contains(s,'low') && ~contains(s,'lower') && ~contains(s,'high'), ig_group{c} = inc_labels{4};
    else,                                                    ig_group{c} = 'Unclassified';
    end
end

IG = struct();
rows_ig = {};
for ig = 1:nIG
    mask = strcmp(ig_group, inc_labels{ig});
    rows_ig{ig} = find(mask);
    sub  = T9(mask, :);
    n_c  = sum(mask);

    IG(ig).IncomeGroup       = inc_labels{ig};
    IG(ig).N_Countries       = n_c;
    IG(ig).Investment_MEur   = sum(sub.Investment_MEur);
    IG(ig).PopShare_Total    = sum(sub.PopShare);
    IG(ig).IncShare_Base     = sum(sub.IncShare_Base);
    IG(ig).IncShare_Final    = sum(sub.IncShare_Final);

    % Within-T: sum of s_c * T_c for group = sum(Contrib)
    IG(ig).TWithin_Contrib_Base   = sum(sub.Contrib_Base);
    IG(ig).TWithin_Contrib_Final  = sum(sub.Contrib_Final);
    IG(ig).TWithin_Contrib_Change = sum(sub.Contrib_Change);

    % Implied group within-T
    IG(ig).TWithin_GroupLevel_Base  = sum(sub.Contrib_Base)  / (sum(sub.IncShare_Base)  + EPS);
    IG(ig).TWithin_GroupLevel_Final = sum(sub.Contrib_Final) / (sum(sub.IncShare_Final) + EPS);

    % Unweighted mean per country
    pos_b = sub.Within_T_Base > 0;
    pos_f = sub.Within_T_Final > 0;
    IG(ig).TWithin_Mean_Base   = mean(sub.Within_T_Base(pos_b));
    IG(ig).TWithin_Mean_Final  = mean(sub.Within_T_Final(pos_f));
    IG(ig).TWithin_Mean_Change = mean(sub.Within_T_Change);

    % Between contribution for group
    IG(ig).TBetween_Contrib_Base   = sum(BC_Base(mask));
    IG(ig).TBetween_Contrib_Final  = sum(BC_Final(mask));
    IG(ig).TBetween_Contrib_Change = sum(BC_Change(mask));

    % Share of countries improving/worsening within-T
    IG(ig).N_Within_Improved = sum(sub.Within_T_Change < 0);
    IG(ig).N_Within_Worsened = sum(sub.Within_T_Change > 0);
end

T_IG = struct2table(IG);
writetable(T_IG, fname_xlsx, 'Sheet', '11_IncGroup_Theil');
fprintf('   Exported: 11_IncGroup_Theil\n');
for ig = 1:nIG
    fprintf('   [%s] n=%d  TWithin_Contrib_Change=%+.2e  TBetween_Contrib_Change=%+.2e\n', ...
        inc_labels{ig}, IG(ig).N_Countries, IG(ig).TWithin_Contrib_Change, IG(ig).TBetween_Contrib_Change);
end
fprintf('\n');

%% D: Region x Theil decomposition
fprintf('[D] Regional x Theil analysis...\n');

regions_all = string(T9.Region);
regions     = unique(regions_all);
regions     = regions(regions ~= "Unclassified" & regions ~= "" & ~ismissing(regions));
nReg = length(regions);

RG = struct();
for r = 1:nReg
    mask = regions_all == regions(r);
    sub  = T9(mask, :);

    RG(r).Region             = char(regions(r));
    RG(r).N_Countries        = sum(mask);
    RG(r).Investment_MEur    = sum(sub.Investment_MEur);
    RG(r).PopShare_Total     = sum(sub.PopShare);
    RG(r).IncShare_Base      = sum(sub.IncShare_Base);
    RG(r).IncShare_Final     = sum(sub.IncShare_Final);
    RG(r).TWithin_Contrib_Base   = sum(sub.Contrib_Base);
    RG(r).TWithin_Contrib_Final  = sum(sub.Contrib_Final);
    RG(r).TWithin_Contrib_Change = sum(sub.Contrib_Change);
    RG(r).TWithin_Mean_Change    = mean(sub.Within_T_Change);
    RG(r).TBetween_Contrib_Base  = sum(BC_Base(mask));
    RG(r).TBetween_Contrib_Final = sum(BC_Final(mask));
    RG(r).TBetween_Contrib_Change= sum(BC_Change(mask));
    RG(r).N_Within_Improved      = sum(sub.Within_T_Change < 0);
    RG(r).N_Within_Worsened      = sum(sub.Within_T_Change > 0);
end

T_RG = struct2table(RG);
writetable(T_RG, fname_xlsx, 'Sheet', '12_Region_Theil');
fprintf('   Exported: 12_Region_Theil\n');
for r = 1:nReg
    fprintf('   [%-35s] n=%2d  dTWithin=%+.2e  dTBetween=%+.2e\n', ...
        RG(r).Region, RG(r).N_Countries, RG(r).TWithin_Contrib_Change, RG(r).TBetween_Contrib_Change);
end
fprintf('\n');

%% J: 4D Triple Asymmetry (GDP / CO2 / Gini / Within-T)
fprintf('[J] Building 4D Triple Asymmetry table...\n');

[~, ia, ib] = intersect(T4.Country, T9.Country, 'stable');
fprintf('   Matched %d / %d countries from TripleAsymmetry.\n', length(ia), height(T4));

T_4D = T4(ia, :);
T_4D.Within_T_Base   = T9.Within_T_Base(ib);
T_4D.Within_T_Final  = T9.Within_T_Final(ib);
T_4D.Within_T_Change = T9.Within_T_Change(ib);
T_4D.BC_Base         = BC_Base(ib);
T_4D.BC_Final        = BC_Final(ib);
T_4D.BC_Change       = BC_Change(ib);
T_4D.IncShare_Base   = T9.IncShare_Base(ib);
T_4D.PopShare        = T9.PopShare(ib);

% Classify each country on 4 dimensions
T_4D.Win_GDP    = T_4D.GDP_Added > 0;
T_4D.Win_CO2    = T_4D.Carbon_Intensity < median(T_4D.Carbon_Intensity(~isnan(T_4D.Carbon_Intensity)));
T_4D.Win_Gini   = T_4D.Gini_Change < 0;
T_4D.Win_Within = T_4D.Within_T_Change < 0;
T_4D.Win_Score  = T_4D.Win_GDP + T_4D.Win_CO2 + T_4D.Win_Gini + T_4D.Win_Within;

writetable(T_4D, fname_xlsx, 'Sheet', '13_TripleAsymm_4D');
fprintf('   Exported: 13_TripleAsymm_4D\n');
win4 = sum(T_4D.Win_Score == 4);
win3 = sum(T_4D.Win_Score == 3);
fprintf('   Countries winning on all 4 dimensions: %d | on 3+: %d\n\n', win4, win4+win3);

%% F-prep: Export Lorenz curve data for Python
fprintf('[F-prep] Exporting Lorenz curve data to Excel...\n');

if exist(fname_mat, 'file')
    wsvars = whos('-file', fname_mat);
    varnames = {wsvars.name};
    if ismember('Lorenz_Base', varnames) && ismember('Lorenz_Final', varnames)
        load(fname_mat, 'Lorenz_Base', 'Lorenz_Final');
        T_Lorenz = table(Lorenz_Base(:,1), Lorenz_Base(:,2), Lorenz_Final(:,2), ...
            'VariableNames', {'Pop_Share', 'Lorenz_Base', 'Lorenz_Final'});
        writetable(T_Lorenz, fname_xlsx, 'Sheet', '14_Lorenz');
        fprintf('   Exported: 14_Lorenz (%d points)\n\n', height(T_Lorenz));
    else
        warning('[F-prep] Lorenz_Base/Final not found in workspace.mat. Skipping sheet 14.');
    end
else
    warning('[F-prep] EUGG_Workspace.mat not found at: %s', fname_mat);
end

%% Summary report
fprintf('=================================================================\n');
fprintf('  EUGG_analysis complete\n');
fprintf('=================================================================\n');
fprintf('Sheets written: 10_Between_Contrib, 10b_Between_Ranked,\n');
fprintf('                11_IncGroup_Theil, 12_Region_Theil,\n');
fprintf('                13_TripleAsymm_4D, 14_Lorenz\n\n');

% Quick Theil contribution summary
fprintf('T_between breakdown by income group:\n');
for ig = 1:nIG
    fprintf('  %-28s dBC=%+.3e\n', inc_labels{ig}, IG(ig).TBetween_Contrib_Change);
end
fprintf('T_within breakdown by income group:\n');
for ig = 1:nIG
    fprintf('  %-28s dTW=%+.3e  (%d impr / %d wors)\n', ...
        inc_labels{ig}, IG(ig).TWithin_Contrib_Change, IG(ig).N_Within_Improved, IG(ig).N_Within_Worsened);
end
fprintf('=================================================================\n');

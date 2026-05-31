% =========================================================================
% EUGG_model.m  |  EU Global Gateway Carbon Inequality Analysis
% Unified model pipeline
%
% Combines:
%   Full Theil T decomposition (between/within, shares, residuals,
%          per-country contributions), South Africa sensitivity, EU struct
%   5 sector-allocation scenarios (S0-S4), 3 technology transfer
%          levels (T0/T25/T10), scenario summary sheets
%
% Output: results/Data/EUGG_Results.xlsx (sheets 1-17) + workspace
%
% Run order:
%   1. EUGG_model.m    → sheets 1–9, 15–17
%   2. EUGG_analysis.m → sheets 10–14
%   3. EUGG_figures.py → all figures
% =========================================================================
clear; clc; close all;
tic;

SCRIPT_DIR = fileparts(mfilename('fullpath'));
if isempty(SCRIPT_DIR)
    SCRIPT_DIR = pwd;
end
INPUT_DIR = fullfile(SCRIPT_DIR, 'data', 'input');
OUTPUT_DIR = fullfile(SCRIPT_DIR, 'results');

fprintf('========================================================\n');
fprintf('   EUGG Carbon Inequality Analysis\n');
fprintf('   Unified: Theil + Scenarios + Tech Transfer\n');
fprintf('========================================================\n\n');

%% SECTION 0: CONFIGURATION
fprintf('[SECTION 0] Configuration...\n');

outputDir = OUTPUT_DIR;
dataDir   = fullfile(outputDir, 'Data');
for d = {outputDir, dataDir}
    if ~exist(d{1}, 'dir'), mkdir(d{1}); end
end

nCountries    = 164; nSectors = 120; N = nCountries * nSectors;
nIncomeGroups = 201;
TARGET_INV_EUR = 300000;  % M EUR (original EUGG commitment)
EUR_USD_2023   = 1.08;    % 2023 average EUR/USD exchange rate (ECB)
TARGET_INV     = TARGET_INV_EUR * EUR_USD_2023;  % M USD (GLORIA unit)
FX             = EUR_USD_2023;  % conversion factor: USD -> EUR (divide by FX)
X_THRESHOLD    = 1.0;     % M USD, minimum valid output node

% Alpha fallback values (income-group step) and EU27 fixed value
ALPHA_HIGH = 0.85; ALPHA_UPPER = 0.65; ALPHA_LOWER = 0.45;
ALPHA_LOW  = 0.30; ALPHA_EU27  = 1.00;

% GLORIA 120-sector index ranges
SEC_AFOLU        = 1:23;  SEC_ENERGY    = 35:42;
SEC_TRANSPORT    = 82:85; SEC_HEAVYMFG  = 43:70;
SEC_CONSTRUCTION = 71;    SEC_SERVICE   = 86:120;

% Sector allocation scenarios
% Weights: [AFOLU, Energy, Transport, HeavyMfg, Construction, Service]
SCENARIOS.S0 = struct('name','Baseline',     'weights',[0.05,0.29,0.17,0.02,0.02,0.45]);
SCENARIOS.S1 = struct('name','ServiceMax',   'weights',[0.05,0.19,0.17,0.02,0.02,0.55]);
SCENARIOS.S2 = struct('name','EnergyMax',    'weights',[0.05,0.39,0.17,0.02,0.02,0.35]);
SCENARIOS.S3 = struct('name','AFOLUMax',     'weights',[0.15,0.19,0.17,0.02,0.02,0.45]);
SCENARIOS.S4 = struct('name','TransportMax', 'weights',[0.05,0.29,0.27,0.02,0.02,0.35]);

% Technology transfer levels
TECH_NAMES   = {'T0','T25','T10'};
TECH_PRCTILE = [0, 25, 10];   % 0 = no transfer; 25 = EU P25; 10 = EU P10
nTech = length(TECH_NAMES);

fprintf('   Scenarios: %d sector x %d tech = %d combinations\n', ...
    length(fieldnames(SCENARIOS)), nTech, length(fieldnames(SCENARIOS))*nTech);
fprintf('   Currency: EUR %.0fB -> USD %.0fB (rate=%.2f)\n', ...
    TARGET_INV_EUR/1000, TARGET_INV/1000, EUR_USD_2023);
fprintf('   Note: GLORIA MRIO tables are in 000 USD -> M USD after /1000.\n');
fprintf('   Investment converted EUR->USD for model; outputs converted back to EUR.\n');
fprintf('   Done.\n\n');

%% SECTION 1: DATA LOADING
fprintf('[SECTION 1] Loading Data...\n');

load(fullfile(INPUT_DIR, 'FD2023.mat'),   'FD');
load(fullfile(INPUT_DIR, 'UT2023.mat'),   'UT');
load(fullfile(INPUT_DIR, 'V2023.mat'),    'v');
load(fullfile(INPUT_DIR, 'va_f.mat'),     'va_f');
load(fullfile(INPUT_DIR, 'CO2_2023.mat'), 'CO2_2023');
load(fullfile(INPUT_DIR, 'C_matrix.mat'), 'C');
C_Global = C(:, 1:nIncomeGroups);

pop_weights_file = fullfile(INPUT_DIR, 'pop_weights.mat');
if exist(pop_weights_file, 'file')
    load(pop_weights_file, 'Pop_Weight_matrix', 'Pop_Weight_global');
    Pop_Weight_global = Pop_Weight_global(:);
    fprintf('   Population weights loaded (164x201 matrix).\n');
else
    warning('[P2] pop_weights.mat not found. Using uniform weights.');
    Pop_Weight_matrix = repmat(ones(1,nIncomeGroups)/nIncomeGroups, nCountries, 1);
    Pop_Weight_global = ones(nIncomeGroups,1)/nIncomeGroups;
end

T_Reg = readtable(fullfile(INPUT_DIR, 'Data.xlsx'), 'Sheet', 'Country and GDP', 'VariableNamingRule', 'preserve');
CountryNames = T_Reg.Country;
if width(T_Reg) >= 5, Income_Groups = string(T_Reg{:,5});
else, Income_Groups = repmat("Unclassified", nCountries, 1); end
Income_Groups(ismissing(Income_Groups)) = "Unclassified";

wb_file    = fullfile(INPUT_DIR, 'World Bank Country Class_2025_10_07.xlsx');
Map_Region = repmat("Unclassified", nCountries, 1);
Map_ISO    = repmat("UNK", nCountries, 1);
if exist(wb_file,'file')
    T_List  = readtable(wb_file,'Sheet','List of economies','VariableNamingRule','preserve');
    T_Map   = readtable(wb_file,'Sheet','Mapping','VariableNamingRule','preserve');
    Map_ISO = string(T_Map.ISO3);
    for i = 1:nCountries
        idx_r = find(strcmp(string(T_List.Code), Map_ISO(i)), 1);
        if ~isempty(idx_r), Map_Region(i) = string(T_List.Region{idx_r});
        elseif contains(Map_ISO(i),'X'), Map_Region(i) = "Rest of World"; end
    end
end

pop_file = fullfile(INPUT_DIR, 'country_population_weights_wb_2023.csv');
Country_Population = zeros(nCountries, 1);
Country_PopShare_External = ones(nCountries, 1) / nCountries;
if exist(pop_file, 'file')
    T_Pop = readtable(pop_file, 'VariableNamingRule', 'preserve');
    if height(T_Pop) ~= nCountries
        error('Population weight file must contain %d rows; found %d.', nCountries, height(T_Pop));
    end
    pop_iso = string(T_Pop.ISO3);
    if any(pop_iso ~= Map_ISO)
        bad_idx = find(pop_iso ~= Map_ISO, 1);
        error('Population ISO order mismatch at row %d: model=%s, population file=%s.', ...
            bad_idx, Map_ISO(bad_idx), pop_iso(bad_idx));
    end
    Country_Population = T_Pop.Population_2023;
    Country_PopShare_External = T_Pop.Country_PopShare_2023;
    if any(isnan(Country_PopShare_External)) || any(Country_PopShare_External < 0)
        error('Population shares contain NaN or negative values.');
    end
    if abs(sum(Country_PopShare_External) - 1) > 1e-8
        error('Population shares must sum to 1; found %.12f.', sum(Country_PopShare_External));
    end
    fprintf('   Country population weights loaded from %s (World Bank SP.POP.TOTL 2023).\n', pop_file);
else
    error('Country population weight file not found: %s. Run build_country_population_weights.py first.', pop_file);
end

fname_inv  = fullfile(INPUT_DIR, 'Investment matrix_GLORIA.xlsx');
P_A        = readmatrix(fname_inv,'Sheet','Initial investment table','Range','C5:UV168');
Inv_Amts   = readmatrix(fname_inv,'Sheet','Initial investment table','Range','C3:UV3');
Proj_Share = readmatrix(fname_inv,'Sheet','Projects share','Range','C6:UV125');
S_NDC      = readmatrix(fname_inv,'Sheet','Share_Demand(S_D)','Range','H2:H165');
S_NDC(isnan(S_NDC)) = 0;
if sum(S_NDC) > 0, S_NDC = S_NDC / sum(S_NDC); end

fprintf('   Done.\n\n');

%% SECTION 2: PREPROCESSING
fprintf('[SECTION 2] Preprocessing...\n');

f = FD/1000; Z = UT/1000; V_mat = v/1000;
VA_vec = sum(V_mat, 1);
X_base = sum(Z, 1) + VA_vec;

valid_idx    = X_base > X_THRESHOLD;
X_base_clean = X_base;
X_base_clean(~valid_idx) = 1e9;

n_neg  = sum(X_base < 0);
n_zero = sum(X_base >= 0 & X_base <= X_THRESHOLD);
fprintf('   X_base: neg=%d, near-zero=%d, total invalid=%d/%d\n', ...
    n_neg, n_zero, sum(~valid_idx), N);

Global_GDP_Base = sum(VA_vec);

CO2_vec        = CO2_2023(:) / 1000;
global_avg_int = sum(CO2_vec) / sum(X_base_clean(valid_idx));
co2_int_raw    = CO2_vec' ./ X_base_clean;
sector_avg_int = zeros(1, nSectors);
for s = 1:nSectors
    rows_s  = s:nSectors:N;
    valid_s = valid_idx(rows_s) & ~(co2_int_raw(rows_s) > 0.01);
    if any(valid_s), sector_avg_int(s) = mean(co2_int_raw(rows_s(valid_s)));
    else,            sector_avg_int(s) = global_avg_int; end
end
for s = 1:nSectors
    rows_s = s:nSectors:N;
    out_s  = co2_int_raw(rows_s) > 0.01;
    CO2_vec(rows_s(out_s)) = X_base_clean(rows_s(out_s))' * sector_avg_int(s);
end
Global_CO2_Base = sum(CO2_vec);

EU27_List = {'Austria','Belgium','Bulgaria','Croatia','Cyprus','Czech Republic',...
    'Denmark','Estonia','Finland','France','Germany','Greece','Hungary',...
    'Ireland','Italy','Latvia','Lithuania','Luxembourg','Malta','Netherlands',...
    'Poland','Portugal','Romania','Slovakia','Slovenia','Spain','Sweden'};
EU_Indices = [];
for i = 1:length(EU27_List)
    idx = find(strcmpi(strip(CountryNames), EU27_List{i}));
    if ~isempty(idx), EU_Indices = [EU_Indices; idx]; end
end
nEU = length(EU_Indices);

TechAbsorb = ones(nCountries, 1);
TechAbsorb(EU_Indices) = 1;

non_eu = ~ismember(1:nCountries, EU_Indices');
fprintf('   TechAbsorb: all non-EU = 1.00 (placeholder); EU27 = %.2f\n', ALPHA_EU27);

c_int = CO2_vec ./ X_base_clean';
c_int(~valid_idx) = 0;

fprintf('   Done.\n\n');

%% SECTION 2b: EU CO2 INTENSITY BENCHMARKS
% Compute sector-level EU intensity percentiles for tech transfer
fprintf('[SECTION 2b] Computing EU CO2 intensity benchmarks...\n');

EU_sector_int = zeros(nSectors, nEU);
for i = 1:nEU
    c_idx = EU_Indices(i);
    for s = 1:nSectors
        node = (c_idx-1)*nSectors + s;
        if valid_idx(node) && X_base_clean(node) < 1e8
            EU_sector_int(s,i) = c_int(node);
        end
    end
end

EU_benchmark = zeros(nSectors, nTech);
EU_benchmark(:,1) = Inf;   % T0: no cap
for t = 2:nTech
    for s = 1:nSectors
        vals = EU_sector_int(s, EU_sector_int(s,:) > 0);
        if ~isempty(vals)
            EU_benchmark(s,t) = prctile(vals, TECH_PRCTILE(t));
        else
            EU_benchmark(s,t) = sector_avg_int(s);
        end
    end
end

% Build modified c_int for each tech level
c_int_variants = cell(nTech, 1);
c_int_variants{1} = c_int;
for t = 2:nTech
    c_mod = c_int;
    for c = 1:nCountries
        if ismember(c, EU_Indices), continue; end
        for s = 1:nSectors
            node = (c-1)*nSectors + s;
            if c_mod(node) > EU_benchmark(s,t)
                c_mod(node) = EU_benchmark(s,t);
            end
        end
    end
    c_int_variants{t} = c_mod;
end

for t = 2:nTech
    n_replaced = sum(c_int_variants{t} < c_int & c_int > 0);
    pct = n_replaced / sum(c_int > 0) * 100;
    fprintf('   %s: %d nodes replaced (%.1f%% of active nodes)\n', ...
        TECH_NAMES{t}, n_replaced, pct);
end
fprintf('   Done.\n\n');

%% SECTION 3: BASELINE MODEL
fprintf('[SECTION 3] Building Baseline Model...\n');

A_base = zeros(N, N);
for i = 1:N
    if valid_idx(i)
        col = Z(:,i) / X_base_clean(i);
        col = max(0, col);
        cs  = sum(col);
        if cs > 0.999, col = col * (0.999/cs); end
        A_base(:,i) = col;
    end
end

spec_rad    = max(abs(eigs(sparse(A_base), 1, 'lm')));
col_sum_max = max(sum(A_base, 1));
fprintf('   A_base spectral radius: %.6f\n', spec_rad);
fprintf('   A_base max column sum:  %.6f\n', col_sum_max);

I_mat  = speye(N);
L_base = I_mat / (I_mat - sparse(A_base));

% Pre-compute baseline emission multiplier for each tech level
e_vec_base_variants = cell(nTech, 1);
for t = 1:nTech
    e_vec_base_variants{t} = c_int_variants{t}' * L_base;
end
fprintf('   Baseline emission multipliers computed for %d tech levels.\n', nTech);

fprintf('   Done.\n\n');

%% SECTION 4: EU TECHNOLOGY MATRIX
fprintf('[SECTION 4] Building EU Technology...\n');

Z_EU_agg = zeros(nSectors, nSectors);
X_EU_agg = zeros(nSectors, 1);
for i = 1:nEU
    c_idx = EU_Indices(i);
    col_s = (c_idx-1)*nSectors+1; col_e = c_idx*nSectors;
    X_EU_agg = X_EU_agg + X_base_clean(col_s:col_e)';
    Z_sub    = Z(:, col_s:col_e);
    for s = 1:nSectors
        Z_EU_agg(s,:) = Z_EU_agg(s,:) + sum(Z_sub(s:nSectors:N,:), 1);
    end
end
A_EU_Tech = Z_EU_agg ./ (X_EU_agg' + 1e-9);

EU_X_by_sector = X_EU_agg;
EU_Sec_Share   = EU_X_by_sector / (sum(EU_X_by_sector) + 1e-9);

EU_Country_Sec_Share = zeros(nEU, nSectors);
for i = 1:nEU
    c_idx = EU_Indices(i);
    col_s = (c_idx-1)*nSectors+1; col_e = c_idx*nSectors;
    EU_Country_Sec_Share(i,:) = X_base_clean(col_s:col_e);
end
for s = 1:nSectors
    col_sum = sum(EU_Country_Sec_Share(:,s));
    if col_sum > 1e-9, EU_Country_Sec_Share(:,s) = EU_Country_Sec_Share(:,s) / col_sum;
    else,              EU_Country_Sec_Share(:,s) = 1/nEU; end
end

CFC_Global = reshape(V_mat(6,:), nSectors, nCountries);
S_EU_CFC   = sum(CFC_Global(:, EU_Indices), 2);
if sum(S_EU_CFC)==0, S_EU_CFC = ones(nSectors,1); end
S_EU_CFC   = S_EU_CFC / sum(S_EU_CFC);

fprintf('   Done.\n\n');

%% SECTION 5: INVESTMENT ALLOCATION
fprintf('[SECTION 5] Investment Allocation...\n');

Inv_Per_Country_Base = zeros(nCountries,1);
colsum_PS = sum(Proj_Share,1);
Proj_Share(:, colsum_PS>0) = Proj_Share(:, colsum_PS>0) ./ colsum_PS(colsum_PS>0);

for p = 1:length(Inv_Amts)
    amt = Inv_Amts(p); if amt<=0, continue; end
    inv_rows = find(P_A(:,p)==1);
    if isempty(inv_rows)
        Inv_Per_Country_Base = Inv_Per_Country_Base + S_NDC*amt;
    else
        sub_shares = S_NDC(inv_rows);
        if sum(sub_shares)>0, w = sub_shares/sum(sub_shares);
        else, w = ones(length(inv_rows),1)/length(inv_rows); end
        Inv_Per_Country_Base(inv_rows) = Inv_Per_Country_Base(inv_rows) + w*amt;
    end
end
if sum(Inv_Per_Country_Base)>0
    Inv_Per_Country_Base = Inv_Per_Country_Base * (TARGET_INV/sum(Inv_Per_Country_Base));
else
    Inv_Per_Country_Base = S_NDC * TARGET_INV;
end

Global_Sec_Share = zeros(nCountries, nSectors);
for s = 1:nSectors
    rows_s = s:nSectors:N;
    X_s    = X_base_clean(rows_s);
    if sum(X_s)>1e-6, Global_Sec_Share(:,s) = X_s/sum(X_s);
    else,              Global_Sec_Share(:,s) = 1/nCountries; end
end

fprintf('   Done.\n\n');

%% SECTION 6: RUN ALL SCENARIOS
% Outer loop: sector allocation (5 scenarios)
% Inner loop: technology transfer (3 levels)
fprintf('[SECTION 6] Running Scenarios (%d sector x %d tech)...\n', ...
    length(fieldnames(SCENARIOS)), nTech);

nFD_total       = size(f, 2);
nFD_per_country = nFD_total / nCountries;
if mod(nFD_total, nCountries) ~= 0
    warning('[P5] FD columns not divisible by nCountries.');
    nFD_per_country = floor(nFD_per_country);
end
hh_cols = 1:nFD_per_country:nFD_total;
fprintf('   FD: %d total cols, %d per country.\n', nFD_total, nFD_per_country);

scenario_names = fieldnames(SCENARIOS);
AllResults     = struct();

prop = va_f(:);
if mean(prop(prop>0)) > 10, prop = prop/1000; end
prop(prop>0.9) = 0.9;

epsilon = 1e-12;

for sc = 1:length(scenario_names)
    sname    = scenario_names{sc};
    scenario = SCENARIOS.(sname);
    sw       = scenario.weights;
    fprintf('\n   === Scenario %d/%d: %s [%.0f/%.0f/%.0f/%.0f/%.0f/%.0f] ===\n', ...
        sc, length(scenario_names), scenario.name, sw(1)*100, sw(2)*100, ...
        sw(3)*100, sw(4)*100, sw(5)*100, sw(6)*100);

    % Sector shares: distribute scenario weights uniformly within each group
    sector_shares = zeros(nSectors,1);
    sector_shares(SEC_AFOLU)        = sw(1)/length(SEC_AFOLU);
    sector_shares(SEC_ENERGY)       = sw(2)/length(SEC_ENERGY);
    sector_shares(SEC_TRANSPORT)    = sw(3)/length(SEC_TRANSPORT);
    sector_shares(SEC_HEAVYMFG)     = sw(4)/length(SEC_HEAVYMFG);
    sector_shares(SEC_CONSTRUCTION) = sw(5);
    sector_shares(SEC_SERVICE)      = sw(6)/length(SEC_SERVICE);
    sector_shares = sector_shares / sum(sector_shares);

    Z_new = Z; X_new = X_base; q_total = zeros(N,1);
    EU_Backflow_by_sector = zeros(nSectors, 1);

    % --- 6a: Investment shock (non-EU recipients) ---
    for c = 1:nCountries
        inv_amt = Inv_Per_Country_Base(c);
        if inv_amt < 1e-6, continue; end
        idx_s = (c-1)*nSectors+1; idx_e = c*nSectors;
        if sum(X_base_clean(idx_s:idx_e)) < 0.1, continue; end
        if ismember(c, EU_Indices), continue; end

        q_c     = inv_amt * sector_shares;
        q_total(idx_s:idx_e) = q_c;
        alpha_c = TechAbsorb(c);

        Z_loc     = Z(:, idx_s:idx_e);
        Z_loc_agg = zeros(nSectors, nSectors);
        for s = 1:nSectors
            Z_loc_agg(s,:) = sum(Z_loc(s:nSectors:N,:), 1);
        end

        Delta_Z = zeros(N, nSectors);
        for j = 1:nSectors
            out_j = q_c(j); if out_j<1e-9, continue; end
            denom = Z_loc_agg(:,j);
            for s = 1:nSectors
                req_EU    = A_EU_Tech(s,j) * out_j;
                dom_idx   = (c-1)*nSectors + s;
                out_idx   = (c-1)*nSectors + j;
                if X_base_clean(out_idx) < 1e9
                    A_dom = sum(Z(s:nSectors:N, out_idx)) / X_base_clean(out_idx);
                else, A_dom = 0; end
                req_total   = alpha_c*req_EU + (1-alpha_c)*A_dom*out_j;
                if req_total < 1e-9, continue; end

                req_from_EU = alpha_c * req_EU;
                EU_Backflow_by_sector(s) = EU_Backflow_by_sector(s) + req_from_EU;

                req_local = req_total - req_from_EU;
                if req_local < 1e-9, continue; end

                rows_s  = s:nSectors:N;
                dom_cap = X_base_clean(dom_idx);
                if denom(s)>0.5 && req_local<(dom_cap+1e-6)
                    d_slice = (Z_loc(rows_s,j)/denom(s)) * req_local;
                else
                    d_slice = Global_Sec_Share(:,s) * req_local;
                end
                Delta_Z(rows_s,j) = Delta_Z(rows_s,j) + d_slice;
            end
        end
        Z_new(:, idx_s:idx_e) = Z_new(:, idx_s:idx_e) + Delta_Z;
        X_new(idx_s:idx_e)    = X_new(idx_s:idx_e) + q_c';
    end

    % --- 6b: EU backflow ---
    for i = 1:nEU
        c_eu      = EU_Indices(i);
        idx_s     = (c_eu-1)*nSectors+1; idx_e = c_eu*nSectors;
        backflow_c = EU_Backflow_by_sector .* EU_Country_Sec_Share(i,:)';
        X_new(idx_s:idx_e) = X_new(idx_s:idx_e) + backflow_c';
        Delta_Z_EU_sec = A_EU_Tech .* backflow_c';
        for r = 1:nSectors
            if sum(Delta_Z_EU_sec(r,:)) < 1e-9, continue; end
            for k = 1:nEU
                row_r = (EU_Indices(k)-1)*nSectors + r;
                Z_new(row_r, idx_s:idx_e) = Z_new(row_r, idx_s:idx_e) + ...
                    Delta_Z_EU_sec(r,:) * EU_Country_Sec_Share(k, r);
            end
        end
    end

    % --- 6c: Updated A matrix and Leontief inverse ---
    valid_new   = X_new > X_THRESHOLD;
    X_new_clean = X_new;
    X_new_clean(~valid_new) = 1e9;

    A_new = zeros(N,N);
    for i = 1:N
        if valid_new(i)
            col = Z_new(:,i) / X_new_clean(i);
            col = max(0, col);
            cs  = sum(col);
            if cs>0.999, col = col*(0.999/cs); end
            A_new(:,i) = col;
        end
    end
    L_new = I_mat / (I_mat - sparse(A_new));

    % --- 6d: Value added and GDP (emission-independent) ---
    VA_new = VA_vec;
    VA_new(valid_new) = X_new(valid_new) - sum(Z_new(:, valid_new), 1);
    Delta_VA = VA_new - VA_vec;
    Delta_VA(~valid_new) = 0;

    Total_GDP_Added     = sum(Delta_VA);
    Total_GDP_Added_Pos = sum(max(0, Delta_VA));
    GDP_Growth_Pct      = (Total_GDP_Added / Global_GDP_Base) * 100;

    % --- 6e partial: GFCF (emission-independent part) ---
    Delta_F_GFCF = Delta_VA(:) .* prop(:);
    gfcf_ratio = sum(abs(Delta_F_GFCF)) / (sum(Inv_Per_Country_Base) + 1e-9);
    if gfcf_ratio > 2.0
        warning('[FIX-P2] GFCF ratio=%.2f exceeds threshold 2.0.', gfcf_ratio);
    end
    Global_FD_Added = q_total + Delta_F_GFCF;

    % Pre-compute emission-independent country metrics
    Country_GDP_Base_sc  = zeros(nCountries,1);
    Country_GDP_Added_sc = zeros(nCountries,1);
    for c = 1:nCountries
        ss = (c-1)*nSectors+1; se = c*nSectors;
        Country_GDP_Base_sc(c)  = sum(VA_vec(ss:se));
        Country_GDP_Added_sc(c) = sum(Delta_VA(ss:se));
    end

    % EU spillover (output and VA)
    EU_SpilloverOutput_Total = sum(EU_Backflow_by_sector);
    EU_SpilloverVA_Total     = sum(Country_GDP_Added_sc(EU_Indices));
    EU_rows_sc = [];
    for c_eu = EU_Indices'
        EU_rows_sc = [EU_rows_sc, (c_eu-1)*nSectors+1 : c_eu*nSectors];
    end
    Delta_X_EU = X_new(EU_rows_sc) - X_base_clean(EU_rows_sc);

    % Delta_F_Mat (emission-independent)
    Delta_F_Mat = zeros(size(f));
    for i = 1:N
        if sum(f(i,:)) > 0
            Delta_F_Mat(i,:) = Delta_F_GFCF(i) * (f(i,:) / sum(f(i,:)));
        end
    end

    fprintf('      GDP: +%.2f B EUR (%.2f B USD), GFCF ratio: %.3f\n', Total_GDP_Added/1000/FX, Total_GDP_Added/1000, gfcf_ratio);

    % =====================================================================
    % INNER LOOP: TECHNOLOGY TRANSFER LEVELS
    % =====================================================================
    for t = 1:nTech
        tname = TECH_NAMES{t};
        rkey  = [sname '_' tname];
        fprintf('      --- %s / %s ---\n', scenario.name, tname);

        % Emission multipliers for this tech level
        e_vec_base_cur = e_vec_base_variants{t};
        e_vec_new_cur  = c_int_variants{t}' * L_new;

        % --- CO2 ---
        CF_Direct  = e_vec_new_cur * q_total;
        CF_Induced = e_vec_new_cur * Delta_F_GFCF;
        Total_CO2  = CF_Direct + CF_Induced;
        CO2_Growth_Pct = (Total_CO2 / Global_CO2_Base) * 100;

        % --- 6f: Global Gini ---
        FP_cg_base  = zeros(nCountries, nIncomeGroups);
        FP_cg_final = zeros(nCountries, nIncomeGroups);
        for c_sb = 1:nCountries
            f_hh_c = f(:, hh_cols(c_sb));
            FP_cg_base(c_sb,  :) = e_vec_base_cur * (f_hh_c .* C_Global);
            FP_cg_final(c_sb, :) = e_vec_new_cur  * (f_hh_c .* C_Global);
        end

        global_pop_cg = Pop_Weight_matrix .* Country_PopShare_External;
        if sum(global_pop_cg(:)) > epsilon
            global_pop_cg = global_pop_cg / sum(global_pop_cg(:));
        end

        FP_pc_base_mat  = FP_cg_base  ./ (global_pop_cg + epsilon);
        FP_pc_final_mat = FP_cg_final ./ (global_pop_cg + epsilon);

        fppc_b_flat = FP_pc_base_mat(:);
        fppc_f_flat = FP_pc_final_mat(:);
        gpop_flat   = global_pop_cg(:);
        valid_sb    = gpop_flat > 1e-10 & fppc_b_flat >= 0 & fppc_f_flat >= 0 & ...
            ~isnan(fppc_b_flat) & ~isnan(fppc_f_flat) & ...
            ~isinf(fppc_b_flat) & ~isinf(fppc_f_flat);

        Gini_Base  = calc_gini_weighted(fppc_b_flat(valid_sb), gpop_flat(valid_sb));
        Gini_Final = calc_gini_weighted(fppc_f_flat(valid_sb), gpop_flat(valid_sb));

        FP_Base  = sum(FP_cg_base,  1);
        FP_Final = sum(FP_cg_final, 1);

        [Lx_B, Ly_B] = lorenz_curve_weighted(fppc_b_flat(valid_sb), gpop_flat(valid_sb));
        [Lx_F, Ly_F] = lorenz_curve_weighted(fppc_f_flat(valid_sb), gpop_flat(valid_sb));

        fprintf('         Gini: %.5f -> %.5f (Delta=%+.2e)\n', ...
            Gini_Base, Gini_Final, Gini_Final-Gini_Base);

        % --- 6f2: Theil T decomposition ---
        Theil_Total_Base  = calc_theil_T_weighted(fppc_b_flat(valid_sb), gpop_flat(valid_sb));
        Theil_Total_Final = calc_theil_T_weighted(fppc_f_flat(valid_sb), gpop_flat(valid_sb));

        country_pop_share   = zeros(nCountries, 1);
        country_inc_share_b = zeros(nCountries, 1);
        country_inc_share_f = zeros(nCountries, 1);
        Theil_Within_C_Base  = zeros(nCountries, 1);
        Theil_Within_C_Final = zeros(nCountries, 1);

        total_inc_b = sum(fppc_b_flat(valid_sb) .* gpop_flat(valid_sb));
        total_inc_f = sum(fppc_f_flat(valid_sb) .* gpop_flat(valid_sb));
        total_pop   = sum(gpop_flat(valid_sb));

        for c = 1:nCountries
            pop_c = global_pop_cg(c,:)';
            fp_b  = FP_pc_base_mat(c,:)';
            fp_f  = FP_pc_final_mat(c,:)';
            valid_c = pop_c > 1e-10 & fp_b >= 0 & ~isnan(fp_b);

            pop_c_total = sum(pop_c(valid_c));
            country_pop_share(c) = pop_c_total / (total_pop + epsilon);

            inc_c_b = sum(fp_b(valid_c) .* pop_c(valid_c));
            inc_c_f = sum(fp_f(valid_c) .* pop_c(valid_c));
            country_inc_share_b(c) = inc_c_b / (total_inc_b + epsilon);
            country_inc_share_f(c) = inc_c_f / (total_inc_f + epsilon);

            if sum(valid_c) > 1
                Theil_Within_C_Base(c)  = calc_theil_T_weighted(fp_b(valid_c), pop_c(valid_c));
                Theil_Within_C_Final(c) = calc_theil_T_weighted(fp_f(valid_c), pop_c(valid_c));
            end
        end

        valid_country_b = country_pop_share > 1e-15 & country_inc_share_b > 1e-15;
        valid_country_f = country_pop_share > 1e-15 & country_inc_share_f > 1e-15;

        Theil_Between_Base = sum(country_inc_share_b(valid_country_b) .* ...
            log(country_inc_share_b(valid_country_b) ./ country_pop_share(valid_country_b)));
        Theil_Between_Final = sum(country_inc_share_f(valid_country_f) .* ...
            log(country_inc_share_f(valid_country_f) ./ country_pop_share(valid_country_f)));

        Theil_Within_Base  = sum(country_inc_share_b .* Theil_Within_C_Base);
        Theil_Within_Final = sum(country_inc_share_f .* Theil_Within_C_Final);

        % Theil contribution and share computation
        Theil_Contrib_Within_Base  = country_inc_share_b .* Theil_Within_C_Base;
        Theil_Contrib_Within_Final = country_inc_share_f .* Theil_Within_C_Final;

        Theil_Between_Share_Base  = Theil_Between_Base  / (Theil_Total_Base  + epsilon) * 100;
        Theil_Within_Share_Base   = Theil_Within_Base   / (Theil_Total_Base  + epsilon) * 100;
        Theil_Between_Share_Final = Theil_Between_Final / (Theil_Total_Final + epsilon) * 100;
        Theil_Within_Share_Final  = Theil_Within_Final  / (Theil_Total_Final + epsilon) * 100;

        Theil_Resid_Base  = Theil_Total_Base  - Theil_Between_Base  - Theil_Within_Base;
        Theil_Resid_Final = Theil_Total_Final - Theil_Between_Final - Theil_Within_Final;

        fprintf('         Theil: Between %+.2e, Within %+.2e, Resid=%.1e/%.1e\n', ...
            Theil_Between_Final - Theil_Between_Base, ...
            Theil_Within_Final - Theil_Within_Base, ...
            Theil_Resid_Base, Theil_Resid_Final);

        % --- 6h: Per-country Gini and CO2 ---
        Gini_C_Base  = zeros(nCountries,1);
        Gini_C_Final = zeros(nCountries,1);
        Country_CO2_Base  = zeros(nCountries,1);
        Country_CO2_Added = zeros(nCountries,1);
        for c = 1:nCountries
            f_hh_c = f(:, hh_cols(c));
            FP_c_base_vec  = e_vec_base_cur * (f_hh_c .* C_Global);
            FP_c_final_vec = e_vec_new_cur  * (f_hh_c .* C_Global);
            w_c = Pop_Weight_matrix(c,:)';
            FP_c_base_pc   = FP_c_base_vec  ./ (w_c' + epsilon);
            FP_c_final_pc  = FP_c_final_vec ./ (w_c' + epsilon);
            Gini_C_Base(c)  = calc_gini_weighted(FP_c_base_pc, w_c);
            Gini_C_Final(c) = calc_gini_weighted(FP_c_final_pc, w_c);
            Country_CO2_Base(c)  = sum(FP_c_base_vec);
            Country_CO2_Added(c) = sum(FP_c_final_vec) - Country_CO2_Base(c);
        end

        % EU spillover CO2 (emission-dependent)
        EU_SpilloverCO2_Total = sum(e_vec_new_cur(EU_rows_sc) .* max(0, Delta_X_EU), 'all');

        % --- 6k: Pack results ---
        R = struct();
        R.scenario_name = scenario.name;
        R.scenario_weights = sw;
        R.tech_level = tname;

        R.Global.GDP_Added     = Total_GDP_Added;
        R.Global.GDP_Growth    = GDP_Growth_Pct;
        R.Global.GDP_Added_Pos = Total_GDP_Added_Pos;
        R.Global.CO2_Added     = Total_CO2;
        R.Global.CO2_Growth    = CO2_Growth_Pct;
        R.Global.Gini_Base     = Gini_Base;
        R.Global.Gini_Final    = Gini_Final;
        R.Global.Gini_Change   = Gini_Final - Gini_Base;
        R.Global.Lorenz_Base   = [Lx_B,Ly_B];
        R.Global.Lorenz_Final  = [Lx_F,Ly_F];
        R.Global.FP_Base       = FP_Base;
        R.Global.FP_Final      = FP_Final;
        R.Global.EU_SpilloverOutput = EU_SpilloverOutput_Total;
        R.Global.EU_SpilloverVA     = EU_SpilloverVA_Total;
        R.Global.EU_SpilloverCO2    = EU_SpilloverCO2_Total;
        R.Global.EU_Backflow_by_sector = EU_Backflow_by_sector;

        % Full Theil T decomposition results
        R.Theil.Total_Base       = Theil_Total_Base;
        R.Theil.Total_Final      = Theil_Total_Final;
        R.Theil.Total_Change     = Theil_Total_Final - Theil_Total_Base;
        R.Theil.Between_Base     = Theil_Between_Base;
        R.Theil.Between_Final    = Theil_Between_Final;
        R.Theil.Between_Change   = Theil_Between_Final - Theil_Between_Base;
        R.Theil.Within_Base      = Theil_Within_Base;
        R.Theil.Within_Final     = Theil_Within_Final;
        R.Theil.Within_Change    = Theil_Within_Final - Theil_Within_Base;
        R.Theil.Between_Share_Base  = Theil_Between_Share_Base;
        R.Theil.Within_Share_Base   = Theil_Within_Share_Base;
        R.Theil.Between_Share_Final = Theil_Between_Share_Final;
        R.Theil.Within_Share_Final  = Theil_Within_Share_Final;
        R.Theil.Residual_Base    = Theil_Resid_Base;
        R.Theil.Residual_Final   = Theil_Resid_Final;
        R.Theil.Country_Within_Base    = Theil_Within_C_Base;
        R.Theil.Country_Within_Final   = Theil_Within_C_Final;
        R.Theil.Country_Within_Change  = Theil_Within_C_Final - Theil_Within_C_Base;
        R.Theil.Country_IncShare_Base  = country_inc_share_b;
        R.Theil.Country_IncShare_Final = country_inc_share_f;
        R.Theil.Country_PopShare       = country_pop_share;
        R.Theil.Country_Contrib_Base   = Theil_Contrib_Within_Base;
        R.Theil.Country_Contrib_Final  = Theil_Contrib_Within_Final;
        R.Theil.Country_Contrib_Change = Theil_Contrib_Within_Final - Theil_Contrib_Within_Base;

        R.Country.Names       = CountryNames;
        R.Country.ISO3        = Map_ISO;
        R.Country.Region      = Map_Region;
        R.Country.IncomeGroup = Income_Groups;
        R.Country.TechAbsorb  = TechAbsorb;
        R.Country.Population  = Country_Population;
        R.Country.PopShare    = Country_PopShare_External;
        R.Country.Investment  = Inv_Per_Country_Base;
        R.Country.GDP_Base    = Country_GDP_Base_sc;
        R.Country.GDP_Added   = Country_GDP_Added_sc;
        R.Country.CO2_Base    = Country_CO2_Base;
        R.Country.CO2_Added   = Country_CO2_Added;
        R.Country.Gini_Base   = Gini_C_Base;
        R.Country.Gini_Final  = Gini_C_Final;
        R.Country.Gini_Change = Gini_C_Final - Gini_C_Base;

        AllResults.(rkey) = R;

        fprintf('         CO2: +%.2f Mt | EU spill: VA=%.0f M, CO2=%.3f Mt\n', ...
            Total_CO2, EU_SpilloverVA_Total, EU_SpilloverCO2_Total);

        % --- S0_T0 only: detailed analysis for backward compatibility ---
        if sc == 1 && t == 1
            % South Africa sensitivity
            ZAF_idx = find(strcmpi(strip(CountryNames), 'South Africa'));
            if isempty(ZAF_idx), ZAF_idx = find(Map_ISO == "ZAF", 1); end
            Sens = struct();
            if ~isempty(ZAF_idx)
                fprintf('         [SENS] South Africa sensitivity (idx=%d, inv=%.0f M EUR)...\n', ...
                    ZAF_idx, Inv_Per_Country_Base(ZAF_idx)/FX);
                gpop_exZAF = global_pop_cg; gpop_exZAF(ZAF_idx,:) = 0;
                fppc_b_exZAF = FP_pc_base_mat; fppc_b_exZAF(ZAF_idx,:) = 0;
                fppc_f_exZAF = FP_pc_final_mat; fppc_f_exZAF(ZAF_idx,:) = 0;
                gpop_exZAF_flat = gpop_exZAF(:);
                fppc_b_exZAF_flat = fppc_b_exZAF(:);
                fppc_f_exZAF_flat = fppc_f_exZAF(:);
                valid_exZAF = gpop_exZAF_flat > 1e-10 & fppc_b_exZAF_flat >= 0 & ~isnan(fppc_b_exZAF_flat);
                Sens.ExZAF_Gini_Base  = calc_gini_weighted(fppc_b_exZAF_flat(valid_exZAF), gpop_exZAF_flat(valid_exZAF));
                Sens.ExZAF_Gini_Final = calc_gini_weighted(fppc_f_exZAF_flat(valid_exZAF), gpop_exZAF_flat(valid_exZAF));
                Sens.ExZAF_Gini_Change = Sens.ExZAF_Gini_Final - Sens.ExZAF_Gini_Base;
                fprintf('         [SENS] Exclude ZAF: Gini %.5f -> %.5f (d=%+.2e)\n', ...
                    Sens.ExZAF_Gini_Base, Sens.ExZAF_Gini_Final, Sens.ExZAF_Gini_Change);
            else
                Sens.ExZAF_Gini_Base = NaN; Sens.ExZAF_Gini_Final = NaN; Sens.ExZAF_Gini_Change = NaN;
            end
            AllResults.S0_T0.Sensitivity = Sens;

            % Alpha sub-dimension placeholder
            AlphaDim = struct('n', 0, 'r', NaN(1,4), 'p', NaN(1,4), ...
                'labels', {{'HCI','Governance','Infrastructure','Finance'}});
            AllResults.S0_T0.AlphaDim = AlphaDim;

            % EU struct for backward compatibility
            EU_GC  = Gini_C_Final(EU_Indices) - Gini_C_Base(EU_Indices);
            EU_GB  = Gini_C_Base(EU_Indices);
            EU_GF  = Gini_C_Final(EU_Indices);
            EU_Nam = CountryNames(EU_Indices);
            EU_GDP_Added = Country_GDP_Added_sc(EU_Indices);
            EU_Inv_Alloc = Inv_Per_Country_Base(EU_Indices);

            AllResults.S0_T0.EU.Names              = EU_Nam;
            AllResults.S0_T0.EU.Gini_Base          = EU_GB;
            AllResults.S0_T0.EU.Gini_Final         = EU_GF;
            AllResults.S0_T0.EU.Gini_Change        = EU_GC;
            AllResults.S0_T0.EU.GDP_Added          = EU_GDP_Added;
            AllResults.S0_T0.EU.Investment         = EU_Inv_Alloc;
            AllResults.S0_T0.EU.Avg_Gini_Change    = mean(EU_GC);
            AllResults.S0_T0.EU.Countries_Improved = sum(EU_GC < 0);
            AllResults.S0_T0.EU.Countries_Worsened = sum(EU_GC > 0);
            AllResults.S0_T0.EU.SpilloverVA_Total     = EU_SpilloverVA_Total;
            AllResults.S0_T0.EU.SpilloverOutput_Total = EU_SpilloverOutput_Total;
            AllResults.S0_T0.EU.SpilloverCO2_Total    = EU_SpilloverCO2_Total;

            % Income group Gini
            inc_classes = ["High","Upper","Lower","Low"];
            IncGrp_Inv = zeros(4,1); IncGrp_GDP = zeros(4,1);
            IncGrp_CO2 = zeros(4,1); IncGrp_Gini_B = zeros(4,1); IncGrp_Gini_F = zeros(4,1);
            for ig = 1:4
                if ig==1,     mask = contains(lower(Income_Groups),'high') & ~contains(lower(Income_Groups),'upper');
                elseif ig==2, mask = contains(lower(Income_Groups),'upper');
                elseif ig==3, mask = contains(lower(Income_Groups),'lower');
                else,         mask = contains(lower(Income_Groups),'low') & ~contains(lower(Income_Groups),'lower'); end
                IncGrp_Inv(ig) = sum(Inv_Per_Country_Base(mask));
                IncGrp_GDP(ig) = sum(Country_GDP_Added_sc(mask));
                IncGrp_CO2(ig) = sum(Country_CO2_Added(mask));
                c_list = find(mask);
                if ~isempty(c_list)
                    ig_w  = global_pop_cg(c_list, :);
                    ig_fb = FP_pc_base_mat(c_list, :);
                    ig_ff = FP_pc_final_mat(c_list, :);
                    valid_ig = ig_w(:) > 1e-10 & ig_fb(:) >= 0 & ig_ff(:) >= 0 & ...
                        ~isnan(ig_fb(:)) & ~isnan(ig_ff(:));
                    IncGrp_Gini_B(ig) = calc_gini_weighted(ig_fb(valid_ig), ig_w(valid_ig));
                    IncGrp_Gini_F(ig) = calc_gini_weighted(ig_ff(valid_ig), ig_w(valid_ig));
                end
            end
            AllResults.S0_T0.IncomeGroup.Names = inc_classes;
            AllResults.S0_T0.IncomeGroup.Investment = IncGrp_Inv;
            AllResults.S0_T0.IncomeGroup.GDP_Added = IncGrp_GDP;
            AllResults.S0_T0.IncomeGroup.CO2_Added = IncGrp_CO2;
            AllResults.S0_T0.IncomeGroup.Gini_Base = IncGrp_Gini_B;
            AllResults.S0_T0.IncomeGroup.Gini_Final = IncGrp_Gini_F;
            AllResults.S0_T0.IncomeGroup.Gini_Change = IncGrp_Gini_F - IncGrp_Gini_B;

            % Regional Gini
            unique_reg = unique(Map_Region); unique_reg = unique_reg(unique_reg ~= "Unclassified");
            nReg = length(unique_reg);
            Reg_Inv = zeros(nReg,1); Reg_GDP = zeros(nReg,1);
            Reg_CO2 = zeros(nReg,1); Reg_Gini_B = zeros(nReg,1); Reg_Gini_F = zeros(nReg,1);
            for r = 1:nReg
                mask   = Map_Region == unique_reg(r);
                Reg_Inv(r) = sum(Inv_Per_Country_Base(mask));
                Reg_GDP(r) = sum(Country_GDP_Added_sc(mask));
                Reg_CO2(r) = sum(Country_CO2_Added(mask));
                c_list = find(mask);
                if ~isempty(c_list)
                    r_w  = global_pop_cg(c_list, :);
                    r_fb = FP_pc_base_mat(c_list, :);
                    r_ff = FP_pc_final_mat(c_list, :);
                    valid_r = r_w(:) > 1e-10 & r_fb(:) >= 0 & r_ff(:) >= 0 & ...
                        ~isnan(r_fb(:)) & ~isnan(r_ff(:));
                    Reg_Gini_B(r) = calc_gini_weighted(r_fb(valid_r), r_w(valid_r));
                    Reg_Gini_F(r) = calc_gini_weighted(r_ff(valid_r), r_w(valid_r));
                end
            end
            AllResults.S0_T0.Region.Names = unique_reg;
            AllResults.S0_T0.Region.Investment = Reg_Inv;
            AllResults.S0_T0.Region.GDP_Added = Reg_GDP;
            AllResults.S0_T0.Region.CO2_Added = Reg_CO2;
            AllResults.S0_T0.Region.Gini_Base = Reg_Gini_B;
            AllResults.S0_T0.Region.Gini_Final = Reg_Gini_F;
            AllResults.S0_T0.Region.Gini_Change = Reg_Gini_F - Reg_Gini_B;
        end
    end  % end tech transfer loop
end  % end scenario loop

fprintf('\n   All scenarios complete.\n\n');

%% SECTION 9: EXPORT
fprintf('[SECTION 9] Exporting Results...\n');
fname_xlsx = fullfile(dataDir, 'EUGG_Results.xlsx');

% FX defined in Section 0: divide M USD by FX to get M EUR for reporting.

% =====================================================================
% A. Backward-compatible sheets (1-9) from S0_T0
% =====================================================================
R0 = AllResults.S0_T0;

T_Global = table();
T_Global.Scenario{1}             = R0.scenario_name;
T_Global.Tech_Level{1}           = R0.tech_level;
T_Global.GDP_Billion(1)          = R0.Global.GDP_Added/1000/FX;
T_Global.GDP_Billion_PosOnly(1)  = R0.Global.GDP_Added_Pos/1000/FX;
T_Global.GDP_Growth_Pct(1)       = R0.Global.GDP_Growth;
T_Global.CO2_Mt(1)               = R0.Global.CO2_Added;
T_Global.CO2_Growth_Pct(1)       = R0.Global.CO2_Growth;
T_Global.Gini_Base(1)            = R0.Global.Gini_Base;
T_Global.Gini_Final(1)           = R0.Global.Gini_Final;
T_Global.Gini_Change(1)          = R0.Global.Gini_Change;
T_Global.EU_SpilloverVA_MEUR(1)  = R0.Global.EU_SpilloverVA/FX;
T_Global.EU_SpilloverOut_MEUR(1) = R0.Global.EU_SpilloverOutput/FX;
T_Global.EU_SpilloverCO2_Mt(1)   = R0.Global.EU_SpilloverCO2;
writetable(T_Global, fname_xlsx, 'Sheet','1_Global');

T_Country = table();
T_Country.ID              = (1:nCountries)';
T_Country.Country         = R0.Country.Names;
T_Country.ISO3            = R0.Country.ISO3;
T_Country.Region          = R0.Country.Region;
T_Country.IncomeGroup     = R0.Country.IncomeGroup;
T_Country.TechAbsorption  = R0.Country.TechAbsorb;
T_Country.Population_2023 = R0.Country.Population;
T_Country.PopShare        = R0.Country.PopShare;
T_Country.Investment_MEur = R0.Country.Investment/FX;
T_Country.GDP_Base        = R0.Country.GDP_Base/FX;
T_Country.GDP_Added       = R0.Country.GDP_Added/FX;
T_Country.Gini_Base       = R0.Country.Gini_Base;
T_Country.Gini_Final      = R0.Country.Gini_Final;
T_Country.Gini_Change     = R0.Country.Gini_Change;
writetable(T_Country, fname_xlsx, 'Sheet','2_Countries');

GDP_Mult_export  = R0.Country.GDP_Added ./ (R0.Country.Investment + 1e-9);
GDP_Mult_export(R0.Country.Investment < 100) = NaN;
CI_export = R0.Country.CO2_Added ./ (R0.Country.GDP_Added + 1e-9);
CI_export(R0.Country.GDP_Added < 0.01 | R0.Country.Investment < 100) = NaN;

T_Asymmetry = table();
T_Asymmetry.Country          = R0.Country.Names;
T_Asymmetry.ISO3             = R0.Country.ISO3;
T_Asymmetry.Region           = R0.Country.Region;
T_Asymmetry.IncomeGroup      = R0.Country.IncomeGroup;
T_Asymmetry.TechAbsorption   = R0.Country.TechAbsorb;
T_Asymmetry.Population_2023  = R0.Country.Population;
T_Asymmetry.PopShare         = R0.Country.PopShare;
T_Asymmetry.Investment_MEur  = R0.Country.Investment/FX;
T_Asymmetry.GDP_Added        = R0.Country.GDP_Added/FX;
T_Asymmetry.GDP_Multiplier   = GDP_Mult_export;
T_Asymmetry.CO2_Added        = R0.Country.CO2_Added;
T_Asymmetry.Carbon_Intensity = CI_export;
T_Asymmetry.Gini_Change      = R0.Country.Gini_Change;
writetable(T_Asymmetry, fname_xlsx, 'Sheet','4_TripleAsymmetry');

% EU27 spillover sheet
EU_GC  = R0.EU.Gini_Change;
EU_GB  = R0.EU.Gini_Base;
EU_GF  = R0.EU.Gini_Final;
EU_Nam = R0.EU.Names;
EU_GDP = R0.EU.GDP_Added;
EU_Inv = R0.EU.Investment;

T_EU = table(EU_Nam, EU_GB, EU_GF, EU_GC, EU_GDP/FX, EU_Inv/FX, ...
    'VariableNames',{'Country','Gini_Base','Gini_Final','Gini_Change','GDP_SpilloverVA_MEUR','Investment_MEUR'});
writetable(T_EU, fname_xlsx, 'Sheet','5_EU27_Spillover');

% EU backflow by sector
T_Backflow = table((1:nSectors)', R0.Global.EU_Backflow_by_sector/FX, ...
    'VariableNames',{'Sector_ID','Backflow_MEUR'});
writetable(T_Backflow, fname_xlsx, 'Sheet','6_EU_Backflow_Sector');

% Sensitivity sheet
if isfield(R0, 'Sensitivity')
    T_Sens = table();
    T_Sens.Scenario = {'Full model'; 'Exclude South Africa'};
    T_Sens.Gini_Base  = [R0.Global.Gini_Base; R0.Sensitivity.ExZAF_Gini_Base];
    T_Sens.Gini_Final = [R0.Global.Gini_Final; R0.Sensitivity.ExZAF_Gini_Final];
    T_Sens.Gini_Change = [R0.Global.Gini_Change; R0.Sensitivity.ExZAF_Gini_Change];
    T_Sens.Countries_Improved = [sum(R0.Country.Gini_Change<0); NaN];
    T_Sens.Avg_DGini      = [mean(R0.Country.Gini_Change); NaN];
    writetable(T_Sens, fname_xlsx, 'Sheet','7_Sensitivity');
end

% Sheet 8: Global Theil T decomposition summary (6 rows)
T_Theil_Global = table();
T_Theil_Global.Metric = { ...
    'Theil_T_Total'; 'Theil_T_Between'; 'Theil_T_Within'; ...
    'Between_Share_Pct'; 'Within_Share_Pct'; 'Decomposition_Residual'};
T_Theil_Global.Baseline = [ ...
    R0.Theil.Total_Base; R0.Theil.Between_Base; R0.Theil.Within_Base; ...
    R0.Theil.Between_Share_Base; R0.Theil.Within_Share_Base; R0.Theil.Residual_Base];
T_Theil_Global.PostInvestment = [ ...
    R0.Theil.Total_Final; R0.Theil.Between_Final; R0.Theil.Within_Final; ...
    R0.Theil.Between_Share_Final; R0.Theil.Within_Share_Final; R0.Theil.Residual_Final];
T_Theil_Global.Change = T_Theil_Global.PostInvestment - T_Theil_Global.Baseline;
writetable(T_Theil_Global, fname_xlsx, 'Sheet','8_Theil_Global');

% Sheet 9: Per-country Theil decomposition (with Contrib columns)
T_Theil_Country = table();
T_Theil_Country.ID              = (1:nCountries)';
T_Theil_Country.Country         = R0.Country.Names;
T_Theil_Country.ISO3            = R0.Country.ISO3;
T_Theil_Country.Region          = R0.Country.Region;
T_Theil_Country.IncomeGroup     = R0.Country.IncomeGroup;
T_Theil_Country.Investment_MEur = R0.Country.Investment/FX;
T_Theil_Country.Population_2023 = R0.Country.Population;
T_Theil_Country.PopShare        = R0.Theil.Country_PopShare;
T_Theil_Country.IncShare_Base   = R0.Theil.Country_IncShare_Base;
T_Theil_Country.IncShare_Final  = R0.Theil.Country_IncShare_Final;
T_Theil_Country.Within_T_Base   = R0.Theil.Country_Within_Base;
T_Theil_Country.Within_T_Final  = R0.Theil.Country_Within_Final;
T_Theil_Country.Within_T_Change = R0.Theil.Country_Within_Change;
T_Theil_Country.Contrib_Base    = R0.Theil.Country_Contrib_Base;
T_Theil_Country.Contrib_Final   = R0.Theil.Country_Contrib_Final;
T_Theil_Country.Contrib_Change  = R0.Theil.Country_Contrib_Change;
writetable(T_Theil_Country, fname_xlsx, 'Sheet','9_Theil_Countries');

% =====================================================================
% B. Scenario summary sheet (all 15 combinations)
% =====================================================================
fprintf('   Writing scenario summary...\n');

all_keys = fieldnames(AllResults);
nComb = length(all_keys);

T_Summary = table();
for k = 1:nComb
    key = all_keys{k};
    Rk  = AllResults.(key);
    T_Summary.Scenario{k}          = Rk.scenario_name;
    T_Summary.Tech_Level{k}        = Rk.tech_level;
    T_Summary.Key{k}               = key;
    T_Summary.GDP_Billion(k)       = Rk.Global.GDP_Added / 1000 / FX;
    T_Summary.CO2_Mt(k)            = Rk.Global.CO2_Added;
    T_Summary.CO2_Growth_Pct(k)    = Rk.Global.CO2_Growth;
    T_Summary.Gini_Base(k)         = Rk.Global.Gini_Base;
    T_Summary.Gini_Final(k)        = Rk.Global.Gini_Final;
    T_Summary.Gini_Change(k)       = Rk.Global.Gini_Change;
    T_Summary.Theil_Total_Change(k)   = Rk.Theil.Total_Change;
    T_Summary.Theil_Between_Change(k) = Rk.Theil.Between_Change;
    T_Summary.Theil_Within_Change(k)  = Rk.Theil.Within_Change;
    T_Summary.EU_SpilloverVA_MEUR(k)  = Rk.Global.EU_SpilloverVA/FX;
    T_Summary.EU_SpilloverCO2_Mt(k)   = Rk.Global.EU_SpilloverCO2;
    T_Summary.Countries_Gini_Improved(k) = sum(Rk.Country.Gini_Change < 0);
end
writetable(T_Summary, fname_xlsx, 'Sheet','15_Scenario_Summary');

% =====================================================================
% C. Per-country Gini change matrix across scenarios
% =====================================================================
fprintf('   Writing per-country Gini matrix...\n');

T_CGini = table();
T_CGini.ID          = (1:nCountries)';
T_CGini.Country     = R0.Country.Names;
T_CGini.ISO3        = R0.Country.ISO3;
T_CGini.Region      = R0.Country.Region;
T_CGini.IncomeGroup = R0.Country.IncomeGroup;
T_CGini.Population_2023 = R0.Country.Population;
T_CGini.PopShare    = R0.Country.PopShare;
T_CGini.Investment  = R0.Country.Investment/FX;
for k = 1:nComb
    key = all_keys{k};
    Rk  = AllResults.(key);
    T_CGini.(key) = Rk.Country.Gini_Change;
end
writetable(T_CGini, fname_xlsx, 'Sheet','16_Country_Gini_Scenarios');

% =====================================================================
% D. Per-country CO2 change matrix across scenarios
% =====================================================================
fprintf('   Writing per-country CO2 matrix...\n');

T_CCO2 = table();
T_CCO2.ID          = (1:nCountries)';
T_CCO2.Country     = R0.Country.Names;
T_CCO2.ISO3        = R0.Country.ISO3;
T_CCO2.Region      = R0.Country.Region;
T_CCO2.IncomeGroup = R0.Country.IncomeGroup;
T_CCO2.Population_2023 = R0.Country.Population;
T_CCO2.PopShare    = R0.Country.PopShare;
T_CCO2.Investment  = R0.Country.Investment/FX;
for k = 1:nComb
    key = all_keys{k};
    Rk  = AllResults.(key);
    T_CCO2.(key) = Rk.Country.CO2_Added;
end
writetable(T_CCO2, fname_xlsx, 'Sheet','17_Country_CO2_Scenarios');

fprintf('   Excel: %s\n', fname_xlsx);

% Save workspace
fname_mat = fullfile(dataDir, 'EUGG_Workspace.mat');
Lorenz_Base  = R0.Global.Lorenz_Base;
Lorenz_Final = R0.Global.Lorenz_Final;
save(fname_mat, 'AllResults', 'SCENARIOS', 'TECH_NAMES', 'TECH_PRCTILE', ...
    'EU_benchmark', 'c_int_variants', ...
    'CountryNames', 'Income_Groups', 'Map_Region', 'Map_ISO', ...
    'Country_Population', 'Country_PopShare_External', ...
    'TechAbsorb', 'A_EU_Tech', 'EU_Country_Sec_Share', 'EU_Backflow_by_sector', ...
    'Global_GDP_Base', 'Global_CO2_Base', ...
    'Lorenz_Base', 'Lorenz_Final', ...
    '-v7.3');
fprintf('   Workspace: %s\n\n', fname_mat);

%% SECTION 10: REPORT
elapsed = toc;
fprintf('========================================================\n');
fprintf('              EUGG ANALYSIS REPORT\n');
fprintf('========================================================\n');

% Baseline (S0_T0) summary
fprintf('\n--- Baseline (S0_T0) ---\n');
fprintf('Investment:          EUR %.0f Billion (USD %.0f Billion)\n', sum(R0.Country.Investment)/1000/FX, sum(R0.Country.Investment)/1000);
fprintf('GDP Added (net):     EUR %.2f B (USD %.2f B, %.4f%%)\n', R0.Global.GDP_Added/1000/FX, R0.Global.GDP_Added/1000, R0.Global.GDP_Growth);
fprintf('CO2 Added:           %.2f Mt (%.4f%%)\n', R0.Global.CO2_Added, R0.Global.CO2_Growth);
fprintf('Gini:                %.5f -> %.5f (Delta=%.5f)\n', R0.Global.Gini_Base, R0.Global.Gini_Final, R0.Global.Gini_Change);
fprintf('Countries Improved:  %d/%d (%.1f%%)\n', ...
    sum(R0.Country.Gini_Change<0), nCountries, sum(R0.Country.Gini_Change<0)/nCountries*100);
fprintf('--- Theil T Decomposition ---\n');
fprintf('Theil T:             %.6f -> %.6f (Delta=%+.2e)\n', ...
    R0.Theil.Total_Base, R0.Theil.Total_Final, R0.Theil.Total_Change);
fprintf('  Between-country:   %.6f -> %.6f (Delta=%+.2e, %.1f%% -> %.1f%%)\n', ...
    R0.Theil.Between_Base, R0.Theil.Between_Final, R0.Theil.Between_Change, ...
    R0.Theil.Between_Share_Base, R0.Theil.Between_Share_Final);
fprintf('  Within-country:    %.6f -> %.6f (Delta=%+.2e, %.1f%% -> %.1f%%)\n', ...
    R0.Theil.Within_Base, R0.Theil.Within_Final, R0.Theil.Within_Change, ...
    R0.Theil.Within_Share_Base, R0.Theil.Within_Share_Final);
fprintf('EU VA (net):         EUR %.2f M\n',  R0.Global.EU_SpilloverVA/FX);
fprintf('EU CO2:              %.3f Mt\n',      R0.Global.EU_SpilloverCO2);
fprintf('EU Improved:         %d/%d | Avg DGini=%.5f\n', ...
    R0.EU.Countries_Improved, nEU, R0.EU.Avg_Gini_Change);

% Scenario comparison table
fprintf('\n--- All Scenarios ---\n');
fprintf('%-18s %-5s %10s %10s %12s %12s %12s\n', ...
    'Scenario', 'Tech', 'GDP(B)', 'CO2(Mt)', 'dGini', 'dTheil_B', 'dTheil_W');
fprintf('%-18s %-5s %10s %10s %12s %12s %12s\n', ...
    repmat('-',1,18), repmat('-',1,5), repmat('-',1,10), repmat('-',1,10), ...
    repmat('-',1,12), repmat('-',1,12), repmat('-',1,12));
for k = 1:nComb
    key = all_keys{k};
    Rk  = AllResults.(key);
    fprintf('%-18s %-5s %10.2f %10.2f %+12.2e %+12.2e %+12.2e\n', ...
        Rk.scenario_name, Rk.tech_level, ...
        Rk.Global.GDP_Added/1000/FX, Rk.Global.CO2_Added, ...
        Rk.Global.Gini_Change, Rk.Theil.Between_Change, Rk.Theil.Within_Change);
end
fprintf('========================================================\n');
fprintf('Elapsed: %.1f min\n', elapsed/60);
fprintf('========================================================\n\n');

%% HELPER FUNCTIONS

function T = calc_theil_T_weighted(x, w)
    x = x(:); w = w(:);
    valid = x > 0 & ~isnan(x) & ~isnan(w) & w > 0;
    x = x(valid); w = w(valid);
    if isempty(x) || sum(x)==0 || sum(w)==0, T = 0; return; end
    w = w / sum(w);
    s = (x .* w) / sum(x .* w);
    T = sum(s .* log(s ./ (w + 1e-30)));
end

function g = calc_gini_weighted(x, w)
    x = x(:);
    if nargin < 2 || isempty(w), w = ones(size(x)); end
    w = w(:);
    valid = x >= 0 & ~isnan(x) & ~isnan(w) & w > 0;
    x = x(valid); w = w(valid);
    if sum(x)==0 || sum(w)==0, g=0; return; end
    w = w / sum(w);
    [x_s, idx] = sort(x);
    w_s    = w(idx);
    cum_pop = [0; cumsum(w_s)];
    cum_inc = [0; cumsum(x_s .* w_s)] / sum(x_s .* w_s);
    B = trapz(cum_pop, cum_inc);
    g = 1 - 2*B;
end

function [Lx, Ly] = lorenz_curve_weighted(x, w)
    x = x(:);
    if nargin < 2 || isempty(w), w = ones(size(x)); end
    w = w(:);
    valid = x >= 0 & ~isnan(x);
    x = x(valid); w = w(valid);
    w = w / sum(w);
    [x_s, idx] = sort(x);
    w_s = w(idx);
    Lx = [0; cumsum(w_s)];
    if sum(x_s)==0, Ly = Lx;
    else, Ly = [0; cumsum(x_s .* w_s)] / sum(x_s .* w_s); end
end

function g = calc_gini(x)
    v = sort(max(0,x(:)));
    if sum(v)==0, g=0; return; end
    n = length(v);
    cum_pop = (0:n)'/n;
    cum_inc = [0;cumsum(v)]/sum(v);
    B = trapz(cum_pop,cum_inc);
    g = 1-2*B;
end

function [Lx,Ly] = lorenz_curve(x)
    v = sort(max(0,x(:)));
    n = length(v);
    Lx = (0:n)'/n;
    if sum(v)==0, Ly=Lx; else, Ly=[0;cumsum(v)]/sum(v); end
end

function cmap = redblue_cmap(n)
    if nargin<1, n=64; end
    half=floor(n/2);
    r=[linspace(0.12,1,half),linspace(1,0.84,n-half)]';
    g=[linspace(0.47,1,half),linspace(1,0.15,n-half)]';
    b=[linspace(0.71,1,half),linspace(1,0.16,n-half)]';
    cmap=[r,g,b];
end

function out = ternary(cond, a, b)
    if cond, out = a; else, out = b; end
end

% Run the EUGG MATLAB model and extended analysis from the repository root.
clear; clc;

repo_dir = fileparts(mfilename('fullpath'));
if isempty(repo_dir)
    repo_dir = pwd;
end
cd(repo_dir);

run(fullfile(repo_dir, 'EUGG_model_V6_0.m'));
run(fullfile(repo_dir, 'EUGG_Analysis_V6_0.m'));

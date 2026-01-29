{
  description = "Glider - personal data aggregation and journaling app";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
    }:
    {
      # NixOS module for deploying Glider
      nixosModules.default = ./nix/module.nix;
      nixosModules.glider = self.nixosModules.default;
    }
    // flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        packages = {
          glider-web = pkgs.callPackage ./nix/packages/glider-web.nix { };
          glider-operator = pkgs.callPackage ./nix/packages/glider-operator.nix {
            inherit uv2nix pyproject-nix pyproject-build-systems;
          };
          default = self.packages.${system}.glider-web;
        };

        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            nodejs_22
            python313
            uv
          ];
        };
      }
    );
}

{ self }:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.glider;
  inherit (lib)
    mkEnableOption
    mkOption
    mkIf
    types
    literalExpression
    ;
in
{
  options.services.glider = {
    enable = mkEnableOption "Glider personal data app";

    package = {
      web = mkOption {
        type = types.package;
        description = "Glider web package";
        example = literalExpression "inputs.glider.packages.\${pkgs.system}.glider-web";
      };

      operator = mkOption {
        type = types.package;
        description = "Glider operator (Python worker) package";
        example = literalExpression "inputs.glider.packages.\${pkgs.system}.glider-operator";
      };
    };

    # Network
    host = mkOption {
      type = types.str;
      default = "0.0.0.0";
      description = "Host address for the web frontend";
    };

    port = mkOption {
      type = types.port;
      default = 5173;
      description = "Port for the web frontend";
    };

    # Storage
    dataDir = mkOption {
      type = types.path;
      default = "/var/lib/glider";
      description = "Directory for Glider data and secrets";
    };

    # SurrealDB connection
    surrealdb = {
      url = mkOption {
        type = types.str;
        default = "ws://localhost:8000";
        description = "SurrealDB WebSocket URL";
      };

      namespace = mkOption {
        type = types.str;
        default = "glider";
        description = "SurrealDB namespace";
      };

      database = mkOption {
        type = types.str;
        default = "glider";
        description = "SurrealDB database name";
      };
    };

    # Temporal connection
    temporal = {
      address = mkOption {
        type = types.str;
        default = "localhost:7233";
        description = "Temporal server address";
      };

      taskQueue = mkOption {
        type = types.str;
        default = "glider-tasks";
        description = "Temporal task queue name";
      };
    };

    # Temporal UI
    temporalUi = {
      enable = mkOption {
        type = types.bool;
        default = true;
        description = "Enable Temporal UI";
      };

      port = mkOption {
        type = types.port;
        default = 8080;
        description = "Port for Temporal UI";
      };
    };

    # Secrets
    environmentFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "File with environment variables (OAuth secrets, etc.)";
    };
  };

  config = mkIf cfg.enable {
    # User and group
    users.users.glider = {
      isSystemUser = true;
      group = "glider";
      home = cfg.dataDir;
      description = "Glider service user";
    };
    users.groups.glider = { };

    # Data directory
    systemd.tmpfiles.rules = [
      "d '${cfg.dataDir}' 0750 glider glider - -"
      "d '${cfg.dataDir}/secrets' 0700 glider glider - -"
    ];

    # glider-web service
    systemd.services.glider-web = {
      description = "Glider Web Frontend";
      after = [
        "network.target"
        "surrealdb.service"
        "temporal.service"
      ];
      wants = [
        "surrealdb.service"
        "temporal.service"
      ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "glider";
        Group = "glider";
        WorkingDirectory = cfg.dataDir;
        ExecStart = "${cfg.package.web}/bin/glider-web";
        Restart = "always";
        RestartSec = 5;

        # Security hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [ cfg.dataDir ];
      }
      // lib.optionalAttrs (cfg.environmentFile != null) {
        EnvironmentFile = cfg.environmentFile;
      };

      environment = {
        HOST = cfg.host;
        PORT = toString cfg.port;
        SURREALDB_URL = cfg.surrealdb.url;
        SURREALDB_NS = cfg.surrealdb.namespace;
        SURREALDB_DB = cfg.surrealdb.database;
        TEMPORAL_ADDRESS = cfg.temporal.address;
      };
    };

    # glider-worker service
    systemd.services.glider-worker = {
      description = "Glider Temporal Worker";
      after = [
        "network.target"
        "temporal.service"
        "surrealdb.service"
      ];
      requires = [ "temporal.service" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = "glider";
        Group = "glider";
        WorkingDirectory = cfg.dataDir;
        ExecStart = "${cfg.package.operator}/bin/python -m glider.entrypoint_worker";
        Restart = "always";
        RestartSec = 5;

        # Security hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [ cfg.dataDir ];
      }
      // lib.optionalAttrs (cfg.environmentFile != null) {
        EnvironmentFile = cfg.environmentFile;
      };

      environment = {
        TEMPORAL_ADDRESS = cfg.temporal.address;
        TEMPORAL_TASK_QUEUE = cfg.temporal.taskQueue;
        SURREALDB_URL = cfg.surrealdb.url;
        SURREALDB_NS = cfg.surrealdb.namespace;
        SURREALDB_DB = cfg.surrealdb.database;
        # Secrets directory for OAuth tokens
        GLIDER_SECRETS_DIR = "${cfg.dataDir}/secrets";
      };
    };

    # Temporal UI service (optional)
    # NOTE: Consider using https://devenv.sh/services/temporal/#servicestemporalui
    systemd.services.glider-temporal-ui = mkIf cfg.temporalUi.enable {
      description = "Temporal UI for Glider";
      after = [ "temporal.service" ];
      wants = [ "temporal.service" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        DynamicUser = true;
        ExecStart = "${pkgs.temporal-ui-server}/bin/ui-server";
        Restart = "always";
        RestartSec = 5;

        # Security hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
      };

      environment = {
        TEMPORAL_ADDRESS = cfg.temporal.address;
        TEMPORAL_UI_PORT = toString cfg.temporalUi.port;
      };
    };
  };
}

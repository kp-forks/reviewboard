/**
 * An API token.
 */

import {
    type Result,
    spina,
} from '@beanbag/spina';

import {
    type BaseResourceAttrs,
    type BaseResourceResourceData,
    type SerializerMap,
    BaseResource,
} from './baseResourceModel';


/**
 * Attributes for the APIToken model.
 *
 * Version Added:
 *     8.0
 */
export interface APITokenAttrs extends BaseResourceAttrs {
    /**
     * Whether the token is deprecated.
     *
     * This is true if the token was generated by a deprecated token generator.
     */
    deprecated: boolean;

    /** Whether the token is expired. */
    expired: boolean;

    /** The expiration date. */
    expires: string | null;

    /**
     * The date and time at which the token became invalid.
     *
     * This will only be set if ``valid`` is false.
     */
    invalidDate: string | null;

    /**
     * The reason that the token is invalid.
     *
     * This will only be set if ``valid`` is false.
     */
    invalidReason: string | null;

    /** The date and time that the token was last used. */
    lastUsed: string | null;

    /** The local-site URL prefix to use for API requests. */
    localSitePrefix: string | null;

    /** The API token's note field. */
    note: string | null;

    /** The policy structure. */
    policy: unknown;

    /** The API token string itself. */
    tokenValue: string | null;

    /** The username of the user that owns the token. */
    userName: string | null;

    /** Whether the token is valid. */
    valid: boolean;
}


/**
 * Resource data for the APIToken model.
 *
 * Version Added:
 *     8.0
 */
export interface APITokenResourceData extends BaseResourceResourceData {
    expires: string;
    note: string;
    policy: string | unknown;
}


/**
 * An API token.
 */
@spina
export class APIToken extends BaseResource<
    APITokenAttrs,
    APITokenResourceData
> {
    /**
     * Return defaults for the model attributes.
     *
     * Returns:
     *     APITokenAttrs:
     *     The default values for new model instances.
     */
    static defaults(): Result<Partial<APITokenAttrs>> {
        return {
            deprecated: false,
            expired: false,
            expires: null,
            invalidDate: null,
            invalidReason: null,
            lastUsed: null,
            localSitePrefix: null,
            note: null,
            policy: {},
            tokenValue: null,
            userName: null,
            valid: true,
        };
    }

    static rspNamespace = 'api_token';
    static attrToJsonMap: Record<string, string> = {
        invalidDate: 'invalid_date',
        invalidReason: 'invalid_reason',
        lastUsed: 'last_used',
        tokenValue: 'token',
    };
    static deserializedAttrs = [
        'deprecated',
        'expired',
        'expires',
        'invalidDate',
        'invalidReason',
        'lastUsed',
        'note',
        'policy',
        'tokenValue',
        'valid',
    ];
    static serializedAttrs = [
        'expires',
        'note',
        'policy',
    ];

    static serializers: SerializerMap = {
        policy: (value: unknown) => JSON.stringify(value),
    };

    /**
     * The default policy set for new API tokens.
     */
    static defaultPolicies = {
        custom: {
            resources: {
                '*': {
                    allow: ['*'],
                    block: [],
                },
            },
        },
        readOnly: {
            resources: {
                '*': {
                    allow: ['GET', 'HEAD', 'OPTIONS'],
                    block: ['*'],
                },
            },
        },
        readWrite: {},
    };

    /**
     * Return the URL for syncing the model.
     *
     * Returns:
     *     string:
     *     The URL to use when making HTTP requests.
     */
    url(): string {
        const localSitePrefix = this.get('localSitePrefix') || '';
        const username = this.get('userName');
        const url =
            `${SITE_ROOT}${localSitePrefix}api/users/${username}/api-tokens/`;

        return this.isNew() ? url : `${url}${this.id}/`;
    }
}

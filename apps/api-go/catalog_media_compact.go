package main

import (
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

// Protected v2 links keep the same claims and encryption. A leading byte in
// the authenticated plaintext distinguishes compact claims from older JSON.
const compactPaidImageFormat = 1

const (
	compactBanktwo byte = 1 << iota
	compactOriginal
	compactCanonicalAnchor
	compactSourceObject
	compactHashedAsset
	compactImageFlags = compactBanktwo | compactOriginal | compactCanonicalAnchor | compactSourceObject | compactHashedAsset
)

type paidImageUUID [16]byte

func (id paidImageUUID) String() string {
	return fmt.Sprintf("%x-%x-%x-%x-%x", id[:4], id[4:6], id[6:8], id[8:10], id[10:])
}

type compactPaidImageClaims struct {
	Format, Flags                   byte
	IssuedAt, ExpiresAt             int64
	Region                          [2]byte
	Account, Configuration, Article paidImageUUID
	SelectedSource, AnchorSource    paidImageUUID
	CanonicalAnchor                 paidImageUUID
	SourceVehicle, SourceArticle    [32]byte
	ObjectDigest                    [32]byte
	ObjectNamespace                 [8]byte
}

var errInvalidPaidImageClaims = errors.New("invalid paid catalog image reference")

func compactPaidImagePlaintext(ref paidCatalogImageReference) ([]byte, error) {
	claims := compactPaidImageClaims{Format: compactPaidImageFormat, IssuedAt: ref.IssuedAt, ExpiresAt: ref.ExpiresAt}
	copy(claims.Region[:], ref.Region)
	if ref.ProviderSlug == "banktwo" {
		claims.Flags |= compactBanktwo
	}
	if ref.Projection == "source" {
		claims.Flags |= compactOriginal
	}
	var canonical string
	if ref.AnchorCanonicalRevisionID != nil {
		claims.Flags |= compactCanonicalAnchor
		canonical = *ref.AnchorCanonicalRevisionID
	}
	var namespace, digest string
	if suffix, ok := strings.CutPrefix(ref.ObjectKey, "sources/"); ok {
		claims.Flags |= compactSourceObject
		namespace, digest, _ = strings.Cut(suffix, "/")
	} else {
		digest = strings.TrimPrefix(ref.ObjectKey, "procedure-images/")
	}
	for _, field := range []struct {
		dst   []byte
		value string
	}{
		{claims.Account[:], ref.CustomerAccountID},
		{claims.Configuration[:], ref.ConfigurationID},
		{claims.Article[:], ref.CanonicalArticleID},
		{claims.SelectedSource[:], ref.SelectedSourceRevisionID},
		{claims.AnchorSource[:], ref.AnchorSourceRevisionID},
		{claims.CanonicalAnchor[:], canonical},
		{claims.SourceVehicle[:], ref.SourceVehicleRefSHA256},
		{claims.SourceArticle[:], ref.SourceArticleRefSHA256},
		{claims.ObjectNamespace[:], namespace},
		{claims.ObjectDigest[:], digest},
	} {
		if field.value == "" {
			continue // The reserved anchor and object namespace bytes are zero when absent.
		}
		decoded, err := hex.Decode(field.dst, []byte(strings.ReplaceAll(field.value, "-", "")))
		if err != nil || decoded != len(field.dst) {
			return nil, errInvalidPaidImageClaims
		}
	}
	asset := []byte(ref.AssetID)
	if paidCatalogDigestPattern.MatchString(ref.AssetID) {
		claims.Flags |= compactHashedAsset
		var err error
		asset, err = hex.DecodeString(ref.AssetID)
		if err != nil {
			return nil, errInvalidPaidImageClaims
		}
	}
	size := binary.Size(claims)
	raw, err := binary.Append(make([]byte, 0, size+len(asset)), binary.BigEndian, claims)
	if err != nil {
		return nil, errInvalidPaidImageClaims
	}
	return append(raw, asset...), nil
}

func decodeCompactPaidImageClaims(raw []byte) (paidCatalogImageReference, error) {
	var claims compactPaidImageClaims
	size, err := binary.Decode(raw, binary.BigEndian, &claims)
	if err != nil || claims.Format != compactPaidImageFormat || claims.Flags&^compactImageFlags != 0 ||
		len(raw) <= size || len(raw)-size > 256 {
		return paidCatalogImageReference{}, errInvalidPaidImageClaims
	}
	ref := paidCatalogImageReference{
		Version: 2, IssuedAt: claims.IssuedAt, ExpiresAt: claims.ExpiresAt, Region: string(claims.Region[:]),
		CustomerAccountID: claims.Account.String(), ConfigurationID: claims.Configuration.String(),
		CanonicalArticleID: claims.Article.String(), SelectedSourceRevisionID: claims.SelectedSource.String(),
		AnchorSourceRevisionID: claims.AnchorSource.String(), ProviderSlug: "bankone", Projection: "article",
		SourceVehicleRefSHA256: hex.EncodeToString(claims.SourceVehicle[:]),
		SourceArticleRefSHA256: hex.EncodeToString(claims.SourceArticle[:]),
	}
	if claims.Flags&compactBanktwo != 0 {
		ref.ProviderSlug = "banktwo"
	}
	if claims.Flags&compactOriginal != 0 {
		ref.Projection = "source"
	}
	if claims.Flags&compactCanonicalAnchor != 0 {
		canonical := claims.CanonicalAnchor.String()
		ref.AnchorCanonicalRevisionID = &canonical
	} else if claims.CanonicalAnchor != (paidImageUUID{}) {
		return paidCatalogImageReference{}, errInvalidPaidImageClaims
	}
	if claims.Flags&compactSourceObject != 0 {
		ref.ObjectKey = "sources/" + hex.EncodeToString(claims.ObjectNamespace[:]) + "/" + hex.EncodeToString(claims.ObjectDigest[:])
	} else {
		if claims.ObjectNamespace != ([8]byte{}) {
			return paidCatalogImageReference{}, errInvalidPaidImageClaims
		}
		ref.ObjectKey = "procedure-images/" + hex.EncodeToString(claims.ObjectDigest[:])
	}
	asset := raw[size:]
	if claims.Flags&compactHashedAsset != 0 {
		if len(asset) != 32 {
			return paidCatalogImageReference{}, errInvalidPaidImageClaims
		}
		ref.AssetID = hex.EncodeToString(asset)
	} else {
		ref.AssetID = string(asset)
	}
	return ref, nil
}

package main

import (
	"bytes"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

// Protected v2 links keep the same claims and encryption. The leading byte in
// the authenticated plaintext distinguishes binary formats from older JSON.
const (
	compactPaidImageFormat          = 1
	compactCurrentSourceImageFormat = 2
)

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

// These objects use their digest for both the public asset ID and object path,
// and the selected revision is the current anchor. Other links use format 1.
type compactCurrentSourceImageClaims struct {
	Format, Flags                   byte
	IssuedAt                        int64
	Region                          [2]byte
	Account, Configuration, Article paidImageUUID
	Source, CanonicalAnchor         paidImageUUID
	SourceVehicle, SourceArticle    [32]byte
	ObjectDigest                    [32]byte
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
	if claims.Flags&(compactSourceObject|compactHashedAsset) == compactSourceObject|compactHashedAsset &&
		claims.SelectedSource == claims.AnchorSource &&
		bytes.Equal(asset, claims.ObjectDigest[:]) && bytes.Equal(claims.ObjectNamespace[:], claims.ObjectDigest[:8]) {
		current := compactCurrentSourceImageClaims{
			Format: compactCurrentSourceImageFormat, Flags: claims.Flags, IssuedAt: claims.IssuedAt,
			Region: claims.Region, Account: claims.Account, Configuration: claims.Configuration, Article: claims.Article,
			Source: claims.AnchorSource, CanonicalAnchor: claims.CanonicalAnchor,
			SourceVehicle: claims.SourceVehicle, SourceArticle: claims.SourceArticle, ObjectDigest: claims.ObjectDigest,
		}
		return binary.Append(nil, binary.BigEndian, current)
	}
	size := binary.Size(claims)
	raw, err := binary.Append(make([]byte, 0, size+len(asset)), binary.BigEndian, claims)
	if err != nil {
		return nil, errInvalidPaidImageClaims
	}
	return append(raw, asset...), nil
}

func decodeCompactPaidImageClaims(raw []byte) (paidCatalogImageReference, error) {
	if len(raw) > 0 && raw[0] == compactCurrentSourceImageFormat {
		var current compactCurrentSourceImageClaims
		size, err := binary.Decode(raw, binary.BigEndian, &current)
		if err != nil || size != len(raw) ||
			current.Flags&(compactSourceObject|compactHashedAsset) != compactSourceObject|compactHashedAsset {
			return paidCatalogImageReference{}, errInvalidPaidImageClaims
		}
		claims := compactPaidImageClaims{
			Flags: current.Flags, IssuedAt: current.IssuedAt, ExpiresAt: current.IssuedAt + paidCatalogImageLifetimeSeconds,
			Region: current.Region, Account: current.Account, Configuration: current.Configuration, Article: current.Article,
			SelectedSource: current.Source, AnchorSource: current.Source, CanonicalAnchor: current.CanonicalAnchor,
			SourceVehicle: current.SourceVehicle, SourceArticle: current.SourceArticle, ObjectDigest: current.ObjectDigest,
			ObjectNamespace: [8]byte(current.ObjectDigest[:8]),
		}
		return claims.reference(current.ObjectDigest[:])
	}
	var claims compactPaidImageClaims
	size, err := binary.Decode(raw, binary.BigEndian, &claims)
	if err != nil || claims.Format != compactPaidImageFormat || len(raw) <= size {
		return paidCatalogImageReference{}, errInvalidPaidImageClaims
	}
	return claims.reference(raw[size:])
}

func (claims compactPaidImageClaims) reference(asset []byte) (paidCatalogImageReference, error) {
	if claims.Flags&^compactImageFlags != 0 || len(asset) == 0 || len(asset) > 256 {
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
